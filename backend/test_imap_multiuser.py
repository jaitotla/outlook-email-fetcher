"""
Test IMAP Multi-User Functionality
Demonstrates setting up and fetching emails for multiple users
"""
import requests
import json

# Backend URL (adjust if needed)
BACKEND_URL = "http://localhost:5051"

def test_setup_users():
    """Setup 3 test users with IMAP credentials"""
    
    users = [
        {
            "user_id": "user1@example.com",
            "imap_email": "user1@gmail.com",
            "imap_app_password": "aaaa bbbb cccc dddd"
        },
        {
            "user_id": "user2@example.com",
            "imap_email": "user2@gmail.com",
            "imap_app_password": "eeee ffff gggg hhhh"
        },
        {
            "user_id": "user3@example.com",
            "imap_email": "user3@gmail.com",
            "imap_app_password": "iiii jjjj kkkk llll"
        }
    ]
    
    print("=" * 60)
    print("SETTING UP IMAP FOR MULTIPLE USERS")
    print("=" * 60)
    
    for user in users:
        print(f"\n📝 Setting up: {user['user_id']}")
        
        payload = {
            "user_id": user["user_id"],
            "settings": {
                "run_imap_server": True,
                "imap_email": user["imap_email"],
                "imap_app_password": user["imap_app_password"],
                "imap_host": "imap.gmail.com",
                "imap_port": 993,
                # Add other settings as needed
                "llm_provider": "openai",
                "llm_model": "gpt-4o-mini"
            }
        }
        
        try:
            response = requests.post(
                f"{BACKEND_URL}/api/settings",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                print(f"✅ Success: {user['user_id']}")
                data = response.json()
                print(f"   Message: {data.get('message')}")
            else:
                print(f"❌ Error: HTTP {response.status_code}")
                print(f"   Response: {response.text}")
        
        except Exception as e:
            print(f"❌ Exception: {e}")
    
    print("\n" + "=" * 60)


def test_check_status():
    """Check IMAP status for all users"""
    
    print("\n" + "=" * 60)
    print("CHECKING IMAP STATUS")
    print("=" * 60)
    
    try:
        response = requests.get(f"{BACKEND_URL}/api/imap/status")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ Service Available: {data['service_available']}")
            print(f"📊 Total Users: {len(data['users'])}")
            
            for user in data['users']:
                print(f"\n👤 User: {user['user_id']}")
                print(f"   Email: {user['email']}")
                print(f"   Enabled: {user['enabled']}")
                print(f"   Last Check: {user.get('last_check', 'Never')}")
                print(f"   IMAP: {user['imap_host']}:{user['imap_port']}")
        else:
            print(f"❌ Error: HTTP {response.status_code}")
    
    except Exception as e:
        print(f"❌ Exception: {e}")
    
    print("\n" + "=" * 60)


def test_fetch_all_users():
    """Trigger IMAP fetch for all users"""
    
    print("\n" + "=" * 60)
    print("FETCHING EMAILS FOR ALL USERS")
    print("=" * 60)
    
    try:
        response = requests.post(f"{BACKEND_URL}/api/imap/fetch")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ Success!")
            print(f"📊 Total Users: {data['total_users']}")
            print(f"📧 Total Emails: {data['total_emails']}")
            
            print("\n📋 Results:")
            for result in data['results']:
                status = "✅" if result['success'] else "❌"
                print(f"\n{status} {result['user_id']}")
                print(f"   Emails Fetched: {result['emails_fetched']}")
                if result['error']:
                    print(f"   Error: {result['error']}")
        else:
            print(f"❌ Error: HTTP {response.status_code}")
            print(f"   Response: {response.text}")
    
    except Exception as e:
        print(f"❌ Exception: {e}")
    
    print("\n" + "=" * 60)


def test_fetch_single_user():
    """Trigger IMAP fetch for a single user"""
    
    user_id = "user1@example.com"
    
    print("\n" + "=" * 60)
    print(f"FETCHING EMAILS FOR SINGLE USER: {user_id}")
    print("=" * 60)
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/imap/fetch",
            params={"user_id": user_id}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ Success!")
            print(f"📧 Emails Fetched: {data['total_emails']}")
            
            for result in data['results']:
                print(f"\n👤 {result['user_id']}")
                print(f"   Emails: {result['emails_fetched']}")
                if result['error']:
                    print(f"   Error: {result['error']}")
        else:
            print(f"❌ Error: HTTP {response.status_code}")
    
    except Exception as e:
        print(f"❌ Exception: {e}")
    
    print("\n" + "=" * 60)


def test_disable_user():
    """Disable IMAP for a user"""
    
    user_id = "user3@example.com"
    
    print("\n" + "=" * 60)
    print(f"DISABLING IMAP FOR: {user_id}")
    print("=" * 60)
    
    try:
        response = requests.delete(f"{BACKEND_URL}/api/imap/{user_id}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ {data['message']}")
        else:
            print(f"❌ Error: HTTP {response.status_code}")
    
    except Exception as e:
        print(f"❌ Exception: {e}")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test IMAP Multi-User Functionality")
    parser.add_argument("--setup", action="store_true", help="Setup test users")
    parser.add_argument("--status", action="store_true", help="Check IMAP status")
    parser.add_argument("--fetch-all", action="store_true", help="Fetch for all users")
    parser.add_argument("--fetch-one", action="store_true", help="Fetch for one user")
    parser.add_argument("--disable", action="store_true", help="Disable one user")
    parser.add_argument("--all", action="store_true", help="Run all tests")
    
    args = parser.parse_args()
    
    if args.all or args.setup:
        test_setup_users()
    
    if args.all or args.status:
        test_check_status()
    
    if args.all or args.fetch_all:
        test_fetch_all_users()
    
    if args.all or args.fetch_one:
        test_fetch_single_user()
    
    if args.all or args.disable:
        test_disable_user()
    
    if not any(vars(args).values()):
        # No arguments provided, show help
        parser.print_help()
        print("\n" + "=" * 60)
        print("QUICK START")
        print("=" * 60)
        print("\n1. Setup users:")
        print("   python test_imap_multiuser.py --setup")
        print("\n2. Check status:")
        print("   python test_imap_multiuser.py --status")
        print("\n3. Fetch emails for all:")
        print("   python test_imap_multiuser.py --fetch-all")
        print("\n4. Run all tests:")
        print("   python test_imap_multiuser.py --all")
        print("\n" + "=" * 60)
