from datetime import datetime
import time

def test():
    timestamp = 1739911299
    
    # Local time conversion
    local_time = datetime.fromtimestamp(timestamp)
    print(f"Local time: {local_time}")
    
    # UTC time conversion
    utc_time = datetime.utcfromtimestamp(timestamp)
    print(f"UTC time: {utc_time}")
    
    # Current time
    current_time = datetime.now()
    current_utc = datetime.utcnow()
    print(f"Current local time: {current_time}")
    print(f"Current UTC time: {current_utc}")
    
    # Calculate days difference
    days_diff = (current_time - local_time).days
    print(f"Days difference: {days_diff}")
    
    # Current unix timestamp
    current_timestamp = int(time.time())
    print(f"Current timestamp: {current_timestamp}")

if __name__ == "__main__":
    test()