import boto3
import json
from decimal import Decimal
from botocore.exceptions import ClientError
from aws_auth import aws_login
from debug import debug

class Dbase:
    def __init__(self, profile_name=None, region_name='us-east-1'):
        """
        Initialize DynamoDB client
        
        :param profile_name: Name of the AWS profile to use (optional)
        :param region_name: AWS region name (default: us-east-1)
        """
        self.profile_name = profile_name
        self.region_name = region_name
        self.client = None
        self._connect()

    @debug
    def _connect(self):
        """
        Create and store DynamoDB client session
        """
        try:
            # Create a session using the specified profile
            session = boto3.Session(profile_name=self.profile_name, region_name=self.region_name)
            
            # Create DynamoDB client
            self.client = session.client('dynamodb')
            return True
        except Exception as e:
            print(f"Error creating DynamoDB client: {e}")
            self.client = None
            return False

    @debug
    def create_table(self, table_name):
        """
        Create a DynamoDB table with the specified schema
        
        :param table_name: Name of the table to create
        :return: True if table created successfully, False otherwise
        """
        if not self.client:
            if not self._connect():
                return False

        try:
            # Create table
            table = self.client.create_table(
                TableName=table_name,
                KeySchema=[
                    {
                        'AttributeName': 'id',
                        'KeyType': 'HASH'  # Partition key
                    }
                ],
                AttributeDefinitions=[
                    {
                        'AttributeName': 'id',
                        'AttributeType': 'S'
                    }
                ],
                ProvisionedThroughput={
                    'ReadCapacityUnits': 5,
                    'WriteCapacityUnits': 5
                }
            )
            
            # Wait for table to be created
            table.meta.client.get_waiter('table_exists').wait(TableName=table_name)
            print(f"Table {table_name} created successfully")
            return True
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceInUseException':
                print(f"Table {table_name} already exists")
                return True
            else:
                print(f"Error creating table: {e}")
                return False
        except Exception as e:
            print(f"Unexpected error: {e}")
            return False

    @debug
    def add_item(self, table_name, item):
        """
        Add an item to the specified DynamoDB table
        
        :param table_name: Name of the DynamoDB table
        :param item: Dictionary containing the item data
        :return: True if item added successfully, False otherwise
        """
        if not self.client:
            if not self._connect():
                return False

        try:
            # Convert item to DynamoDB format
            def convert_to_dynamodb_format(value):
                if isinstance(value, str):
                    return {'S': value}
                elif isinstance(value, (int, float)):
                    return {'N': str(value)}
                elif isinstance(value, bool):
                    return {'BOOL': value}
                elif isinstance(value, list):
                    return {'L': [convert_to_dynamodb_format(v) for v in value]}
                elif isinstance(value, dict):
                    return {'M': {k: convert_to_dynamodb_format(v) for k, v in value.items()}}
                elif value is None:
                    return {'NULL': True}
                else:
                    return {'S': str(value)}

            # Convert the entire item to DynamoDB format
            dynamodb_item = {k: convert_to_dynamodb_format(v) for k, v in item.items()}
            
            # Add item to table
            self.client.put_item(
                TableName=table_name,
                Item=dynamodb_item
            )
            
            print(f"Successfully added item to table {table_name}")
            return True
            
        except ClientError as e:
            print(f"Error adding item to table: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error: {e}")
            return False

    @debug
    def get_item(self, table_name, item_id):
        """
        Get an item from the specified DynamoDB table
        
        :param table_name: Name of the DynamoDB table
        :param item_id: ID of the item to retrieve
        :return: Item data if found, None otherwise
        """
        if not self.client:
            if not self._connect():
                return None

        try:
            # Get item from table
            response = self.client.get_item(
                TableName=table_name,
                Key={
                    'id': {'S': item_id}
                }
            )
            
            if 'Item' in response:
                return response['Item']
            else:
                print(f"Item {item_id} not found in table {table_name}")
                return None
                
        except ClientError as e:
            print(f"Error getting item from table: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error: {e}")
            return None

    @debug
    def delete_table(self, table_name):
        """
        Delete the specified DynamoDB table
        
        :param table_name: Name of the table to delete
        :return: True if table deleted successfully, False otherwise
        """
        if not self.client:
            if not self._connect():
                return False

        try:
            # Delete table
            self.client.delete_table(TableName=table_name)
            
            # Wait for table to be deleted
            self.client.get_waiter('table_not_exists').wait(TableName=table_name)
            print(f"Table {table_name} deleted successfully")
            return True
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                print(f"Table {table_name} does not exist")
                return True
            else:
                print(f"Error deleting table: {e}")
                return False
        except Exception as e:
            print(f"Unexpected error: {e}")
            return False

    @staticmethod
    def get_table_schema():
        """
        Returns the schema for the products table
        """
        return {
            'id': 'S',  # String (UUID)
            'current_stock': 'N',  # Number
            'name': 'S',  # String
            'category': 'S',  # String
            'style': 'S',  # String
            'description': 'S',  # String
            'price': 'N',  # Number (Decimal)
            'image': 'S',  # String (filename)
            'gender_affinity': 'S',  # String (F/M)
            'where_visible': 'S'  # String (UI/API)
        }

if __name__ == "__main__":
    # Example usage
    table_name = "Products"
    db = Dbase()  # Uses default profile and region
    db.create_table(table_name)
    
    # Using a specific profile
    # db = Dbase(profile_name='my-profile', region_name='us-west-2')
    # db.create_table(table_name) 