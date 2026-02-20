"""
Create the first developer user (run once after db.create_all()).
Usage: set env FLASK_APP=run:app and DB + REDIS + SECRET_KEY, then:
  python scripts/create_developer.py
Or: python -c "exec(open('scripts/create_developer.py').read())" from project root.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import User
from app.config import MAX_DEVELOPER_ACCOUNTS

def main():
    app = create_app()
    with app.app_context():
        n = User.query.filter_by(role="developer", is_active=True).count()
        if n >= MAX_DEVELOPER_ACCOUNTS:
            print("Developer account limit reached. Use Developer dashboard to manage users.")
            return
        username = input("Username: ").strip()
        if not username:
            print("Username required.")
            return
        if User.query.filter_by(username=username).first():
            print("User already exists.")
            return
        from app.utils.validators import validate_password
        while True:
            password = input("Password: ")
            ok, err = validate_password(password)
            if ok:
                break
            print(err)
        full_name = input("Full name (optional): ").strip() or username
        user = User(username=username, full_name=full_name, role="developer", is_active=True, must_change_password=True)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        print("Developer created. They must change password on first login.")

if __name__ == "__main__":
    main()
