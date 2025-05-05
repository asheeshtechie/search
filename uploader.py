import yaml
from dbase import Dbase
import argparse
import sys
import os
from datetime import datetime
from dotenv import load_dotenv
from debug import debug
import boto3
from botocore.exceptions import ClientError

class DataUploader:
    def __init__(self, profile_name=None, region_name='us-east-1'):
        """
        Initialize DataUploader with AWS credentials
        
        :param profile_name: Name of the AWS profile to use (optional)
        :param region_name: AWS region name (default: us-east-1)
        """
        self.profile_name = profile_name
        self.region_name = region_name
        self.db = Dbase(profile_name, region_name)
        self.config = self._load_config()
        # Initialize S3 client
        session = boto3.Session(profile_name=profile_name, region_name=region_name)
        self.s3_client = session.client('s3')

    @debug
    def _load_config(self):
        """
        Load configuration from environment variables
        """
        # Load environment variables from .env file if it exists
        load_dotenv()
        
        # Get paths from environment variables with defaults
        data_path = os.getenv('DATA_PATH', './data')
        image_path = os.getenv('IMAGE_PATH', './data/images')
        s3_bucket = os.getenv('S3_BUCKET')
        
        # Validate required environment variables
        if not s3_bucket:
            raise ValueError("S3_BUCKET environment variable is required")
        
        # Create directories if they don't exist
        os.makedirs(data_path, exist_ok=True)
        os.makedirs(image_path, exist_ok=True)
        
        return {
            'data_path': data_path,
            'image_path': image_path,
            's3_bucket': s3_bucket
        }

    @debug
    def upload_image_to_s3(self, image_path, product, bucket_name):
        """
        Upload an image to S3
        
        :param image_path: Path to the image file
        :param product: Dictionary containing product data
        :param bucket_name: Name of the S3 bucket
        :return: True if upload successful, False otherwise
        """
        try:
            # Check if image file exists
            if not os.path.exists(image_path):
                print(f"Warning: Image file not found: {image_path}")
                return False
                
            # Create S3 key using category as folder
            category = product.get('category', 'uncategorized')
            image_name = product.get('image')
            if not image_name:
                print(f"Warning: No image name found for product {product.get('id')}")
                return False
                
            s3_key = f"{category}/{image_name}"
            
            # Upload file to S3
            try:
                self.s3_client.upload_file(
                    image_path,
                    bucket_name,
                    s3_key,
                    ExtraArgs={
                        'ContentType': 'image/jpeg'  # Adjust based on image type
                    }
                )
                print(f"Successfully uploaded image to S3: {s3_key}")
                return True
                
            except ClientError as e:
                print(f"Error uploading to S3: {e}")
                return False
            
        except Exception as e:
            print(f"Error uploading image to S3: {e}")
            return False

    @debug
    def get_image_path(self, product, base_image_path, default_image='product_image_coming_soon.png'):
        """
        Get the path to the product image, using default if not found
        
        :param product: Dictionary containing product data
        :param base_image_path: Base path for product images
        :param default_image: Name of the default image file
        :return: Tuple of (image_path, is_default)
        """
        if 'image' not in product:
            return os.path.join(base_image_path, default_image), True
            
        category = product.get('category', 'uncategorized')
        image_file_path = os.path.join(base_image_path, category, product['image'])
        
        if not os.path.exists(image_file_path):
            print(f"Warning: Product image not found: {image_file_path}, using default image")
            return os.path.join(base_image_path, default_image), True
            
        return image_file_path, False

    @debug
    def bulk_upload_products(self, yaml_file, table_name, start_index=0, count=None):
        """
        Read products from YAML file and upload them to DynamoDB and S3 with pagination
        
        :param yaml_file: Path to the YAML file containing products
        :param table_name: Name of the DynamoDB table
        :param start_index: Starting index for pagination (default: 0)
        :param count: Number of products to process (default: None, process all)
        """
        try:
            # Construct full path to YAML file
            yaml_path = os.path.join(self.config['data_path'], yaml_file)
            
            # Read YAML file
            with open(yaml_path, 'r') as file:
                products = yaml.safe_load(file)
            
            if not products:
                print("No products found in YAML file")
                return
            
            # Calculate end index
            end_index = start_index + count if count is not None else len(products)
            end_index = min(end_index, len(products))
            
            # Get subset of products based on pagination
            products_subset = products[start_index:end_index]
            
            print(f"\nProcessing products {start_index + 1} to {end_index} of {len(products)}")
            
            # Initialize counters
            db_success = 0
            db_failure = 0
            image_success = 0
            image_failure = 0
            default_image_count = 0
            
            # Process each product
            for product in products_subset:
                # Add timestamp for tracking
                product['created_at'] = datetime.utcnow().isoformat()
                
                # Upload to database
                if self.db.add_item(table_name, product):
                    db_success += 1
                    
                    # Get image path and upload image
                    image_file_path, is_default = self.get_image_path(product, self.config['image_path'])
                    if is_default:
                        default_image_count += 1
                        # Update product with default image name
                        product['image'] = 'product_image_coming_soon.png'
                    
                    if self.upload_image_to_s3(image_file_path, product, self.config['s3_bucket']):
                        image_success += 1
                    else:
                        image_failure += 1
                else:
                    db_failure += 1
            
            # Print summary
            print(f"\nUpload Summary:")
            print(f"Database:")
            print(f"  Successfully uploaded: {db_success}")
            print(f"  Failed to upload: {db_failure}")
            print(f"Images:")
            print(f"  Successfully uploaded: {image_success}")
            print(f"  Failed to upload: {image_failure}")
            print(f"  Using default image: {default_image_count}")
            print(f"Total products processed: {len(products_subset)}")
            
        except FileNotFoundError:
            print(f"Error: File {yaml_file} not found")
            sys.exit(1)
        except yaml.YAMLError as e:
            print(f"Error parsing YAML file: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"Unexpected error: {e}")
            sys.exit(1)

@debug
def main():
    parser = argparse.ArgumentParser(description='Upload products from YAML to DynamoDB and S3')
    parser.add_argument('yaml_file', help='Path to the YAML file containing products')
    parser.add_argument('--table-name', default='Products', help='DynamoDB table name (default: Products)')
    parser.add_argument('--profile', help='AWS profile name')
    parser.add_argument('--region', default='us-east-1', help='AWS region (default: us-east-1)')
    parser.add_argument('--start', type=int, default=0, help='Starting index for pagination (default: 0)')
    parser.add_argument('--count', type=int, help='Number of products to process (default: all)')
    
    args = parser.parse_args()
    
    try:
        # Initialize uploader
        uploader = DataUploader(args.profile, args.region)
        
        # Upload products
        uploader.bulk_upload_products(
            args.yaml_file,
            args.table_name,
            args.start,
            args.count
        )
    except ValueError as e:
        print(f"Configuration error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 