from flask import Flask, render_template, request, flash
from dbase import Dbase
import boto3
from botocore.exceptions import ClientError
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Required for flash messages

# Initialize AWS clients
db = Dbase()
s3_client = boto3.client('s3')

def get_s3_image_url(image_key):
    """Generate a pre-signed URL for the S3 image"""
    try:
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': os.getenv('S3_BUCKET'),
                'Key': image_key
            },
            ExpiresIn=3600  # URL expires in 1 hour
        )
        return url
    except ClientError as e:
        print(f"Error generating presigned URL: {e}")
        return None

@app.route('/', methods=['GET', 'POST'])
def index():
    product = None
    image_url = None
    error = None

    if request.method == 'POST':
        product_id = request.form.get('product_id')
        if product_id:
            # Get product from DynamoDB
            product = db.get_item(os.getenv('DYNAMODB_TABLE_NAME'), product_id)
            
            if product:
                # Convert DynamoDB format to regular dictionary
                product = {k: v.get(list(v.keys())[0]) for k, v in product.items()}
                
                # Get image URL from S3
                if 'image' in product and 'category' in product:
                    image_key = f"{product['category']}/{product['image']}"
                    image_url = get_s3_image_url(image_key)
            else:
                error = "Product not found"

    return render_template('index.html', 
                         product=product, 
                         image_url=image_url, 
                         error=error)

if __name__ == '__main__':
    app.run(debug=True) 