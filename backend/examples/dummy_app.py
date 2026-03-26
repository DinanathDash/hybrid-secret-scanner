def connect_to_database():
    # Local dev credentials - completely safe
    db_password = "local_test_password_123"
    print("Connecting to local DB...")
    return db_password


def get_aws_bucket():
    # Oh no... the developer left a live key in here!
    aws_access_key = "AKIAIOSFODNN7EXAMPLE"
    print("Connecting to S3...")
    return aws_access_key


def check_weather():
    # Just an empty variable placeholder
    api_key = ""
    return api_key
