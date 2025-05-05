from flask import Flask, request, jsonify, render_template
from aws_auth import aws_login
from dbase import Dbase
import json
import os
from dotenv import load_dotenv
import boto3
from botocore.exceptions import ClientError
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Set default values for required environment variables
DEFAULT_TABLE_NAME = 'Products'
DEFAULT_S3_BUCKET = 'productsimageopensearchbucket'
# Validate required environment variables
if not os.getenv('S3_BUCKET'):
    logger.warning(f"S3_BUCKET not set, using default: {DEFAULT_S3_BUCKET}")
    os.environ['S3_BUCKET'] = DEFAULT_S3_BUCKET

if not os.getenv('DYNAMODB_TABLE_NAME'):
    logger.warning(f"DYNAMODB_TABLE_NAME not set, using default: {DEFAULT_TABLE_NAME}")
    os.environ['DYNAMODB_TABLE_NAME'] = DEFAULT_TABLE_NAME

app = Flask(__name__)

# Initialize AWS clients
db = Dbase()
s3_client = boto3.client('s3')

def get_s3_image_url(image_key):
    """Generate a pre-signed URL for the S3 image"""
    try:
        bucket_name = os.getenv('S3_BUCKET', DEFAULT_S3_BUCKET)
        logger.debug(f"Generating presigned URL for bucket: {bucket_name}, key: {image_key}")
        
        # Check if the object exists
        try:
            s3_client.head_object(Bucket=bucket_name, Key=image_key)
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                logger.error(f"Image not found in S3: {image_key}")
                return None
            else:
                raise
        
        # Generate presigned URL
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket_name,
                'Key': image_key
            },
            ExpiresIn=3600  # URL expires in 1 hour
        )
        logger.debug(f"Generated presigned URL: {url}")
        return url
    except Exception as e:
        logger.error(f"Error generating presigned URL: {str(e)}")
        return None

@app.route('/', methods=['GET'])
def index():
    """Serve the main page"""
    return render_template('index.html')

@app.route('/api/aws/login', methods=['POST'])
def login_aws():
    """
    REST API endpoint to authenticate with AWS
    Expected JSON body:
    {
        "profile_name": "optional-profile-name",
        "region_name": "optional-region-name"
    }
    """
    try:
        data = request.get_json()
        profile_name = data.get('profile_name')
        region_name = data.get('region_name', 'us-east-1')
        
        session = aws_login(profile_name, region_name)
        
        if session:
            return jsonify({
                'status': 'success',
                'message': 'Successfully authenticated with AWS',
                'region': region_name
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to authenticate with AWS'
            }), 401
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error during AWS authentication: {str(e)}'
        }), 500

@app.route('/api/dynamodb/create-table', methods=['POST'])
def create_table():
    """
    REST API endpoint to create a DynamoDB table
    Expected JSON body:
    {
        "table_name": "required-table-name",
        "profile_name": "optional-profile-name",
        "region_name": "optional-region-name"
    }
    """
    try:
        data = request.get_json()
        
        # Validate required fields
        if 'table_name' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Missing required field: table_name'
            }), 400
        
        # Extract parameters
        table_name = data['table_name']
        profile_name = data.get('profile_name')
        region_name = data.get('region_name', 'us-east-1')
        
        # Create new Dbase instance with specified profile and region
        db_instance = Dbase(profile_name=profile_name, region_name=region_name)
        
        # Create the table
        success = db_instance.create_table(table_name)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': f'Table {table_name} created successfully',
                'table_name': table_name,
                'schema': Dbase.get_table_schema(),
                'region': region_name
            }), 201
        else:
            return jsonify({
                'status': 'error',
                'message': f'Failed to create table {table_name}'
            }), 500
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error creating DynamoDB table: {str(e)}'
        }), 500

@app.route('/api/products/<product_id>', methods=['GET'])
def get_product(product_id):
    """
    REST API endpoint to get a product by ID
    URL Parameter: product_id
    Returns: Product details and image URL if found
    """
    try:
        table_name = os.getenv('DYNAMODB_TABLE_NAME', DEFAULT_TABLE_NAME)
        logger.debug(f"Getting product {product_id} from table {table_name}")
        
        # Get product from DynamoDB
        product = db.get_item(table_name, product_id)
        
        if product:
            # Convert DynamoDB format to regular dictionary
            product_dict = {k: v.get(list(v.keys())[0]) for k, v in product.items()}
            logger.debug(f"Retrieved product: {product_dict}")
            
            # Get image URL from S3 if image exists
            image_url = None
            if 'image' in product_dict and 'category' in product_dict:
                image_key = f"{product_dict['category']}/{product_dict['image']}"
                logger.debug(f"Looking for image with key: {image_key}")
                image_url = get_s3_image_url(image_key)
                if image_url:
                    product_dict['image_url'] = image_url
                    logger.debug(f"Added image URL to product: {image_url}")
                else:
                    logger.warning(f"No image URL generated for key: {image_key}")
            
            return jsonify({
                'status': 'success',
                'data': product_dict
            }), 200
        else:
            logger.warning(f"Product not found: {product_id}")
            return jsonify({
                'status': 'error',
                'message': 'Product not found'
            }), 404
            
    except Exception as e:
        logger.error(f"Error retrieving product: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error retrieving product: {str(e)}'
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'message': 'Service is running',
        'config': {
            'table_name': os.getenv('DYNAMODB_TABLE_NAME', DEFAULT_TABLE_NAME),
            's3_bucket': os.getenv('S3_BUCKET', DEFAULT_S3_BUCKET)
        }
    }), 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000) 