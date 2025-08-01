
# Django Authentication Project

This is a Django web application that provides user authentication functionality, including user registration, login, logout, and password management.

## Features

- User registration (signup) with validation  
- User login and logout  
- Password hashing for security  
- Simple and clean UI for authentication pages  
- Backend powered by Django's built-in authentication system

## Installation

1. Clone the repository:

   ```bash
   git clone git@github.com:YonathanTAbebe/auth_project.git
   cd auth_project
2. Create and activate a virtual environment:

python3 -m venv env
source env/bin/activate   # On Windows: env\Scripts\activate

3. Install dependencies:

pip install -r requirements.txt

Apply migrations:

python manage.py migrate

Run the development server:

python manage.py runserver

Open your browser and visit http://127.0.0.1:8000
Usage

    Visit /signup to create a new account

    Visit /login to sign in

    Visit /logout to sign out

Contributing

Feel free to submit issues or pull requests.
License

This project is licensed under the MIT License.


---

### Step 4: Save and exit nano

- Press `CTRL + O` to save (it will ask for file name, just press Enter)
- Press `CTRL + X` to exit nano

---

### Step 5: Stage README.md for commit

```bash
git add README.md

Step 6: Commit the changes

git commit -m "Add README.md with project overview"

Step 7: Push to GitHub

git push

