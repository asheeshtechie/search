import boto3
from botocore.exceptions import ClientError, ProfileNotFound

def aws_login(profile_name='default', region_name='us-east-1'):
    """
    Authenticate with AWS using either profile credentials or default credentials
    
    :param profile_name: Name of the AWS profile to use (optional)
    :param region_name: AWS region name (default: us-east-1)
    :return: boto3 session if successful, None if failed
    """
    try:
        if profile_name:
            # Create session using specific profile
            session = boto3.Session(profile_name=profile_name, region_name=region_name)
        else:
            # Create session using default credentials
            session = boto3.Session(region_name=region_name)
        
        # Test the credentials by making a simple API call
        sts = session.client('sts')
        identity = sts.get_caller_identity()
        
        print(f"Successfully authenticated as: {identity['Arn']}")
        print(f"Account ID: {identity['Account']}")
        print(f"Region: {region_name}")
        
        return session
        
    except ProfileNotFound:
        print(f"Error: AWS profile '{profile_name}' not found")
        return None
    except ClientError as e:
        print(f"Error authenticating with AWS: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None

if __name__ == "__main__":
    # Example usage
    # Using default credentials
    session = aws_login()
    
    # Using a specific profile
    # session = aws_login(profile_name='my-profile', region_name='us-west-2') 