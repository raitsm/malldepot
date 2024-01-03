from app import create_app, db
from app.models import User, UserRole
from werkzeug.security import generate_password_hash


def main():
    # Users to be added
    users_data = [
        {"username": "test_adm", 
         "given_name": "Test",
         "surname": "Admin",
         "password": "opopopop", 
         "email": "admin@nowhere", 
         "phone": "+1233525435",
         "role": UserRole.ADMIN},
        {"username": "test_op", 
         "given_name": "Test",
         "surname": "Operator",
         "password": "opopopop", 
         "email": "operator@nowhere",
         "phone": "+1233525435",
         "role": UserRole.OPERATOR},
        {"username": "test_ro",
         "given_name": "Test",
         "surname": "Reader",
         "password": "opopopop", 
         "phone": "+1233525435",
         "email": "ro@nowhere", 
         "role": UserRole.READ_ONLY},
        # Add more users as needed
    ]



    app = create_app()

    with app.app_context():
        # Check if users already exist
        for user_data in users_data:
            user = User.query.filter_by(username=user_data['username']).first()
            if not user:
                new_user = User(username=user_data['username'],
                                email=user_data['email'],
                                given_name=user_data['given_name'],
                                surname=user_data['surname'],
                                phone=user_data['phone'],
                                role=user_data['role'],
                                password_hash=generate_password_hash(user_data['password']))
                db.session.add(new_user)

        db.session.commit()
        print('Users added successfully.')

if __name__ == "__main__":
    # with app.app_context():
        main()
