from datetime import datetime
import uuid
from flask import Flask, jsonify, render_template, request, redirect, url_for, flash,session
import openai
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature
app = Flask(__name__)


app.secret_key = 'your_secret_key'

# Configure MongoDB
client = MongoClient('localhost', 27017)
db = client.user_database
users = db.users
sessions = db.sessions
logins=db.logins

from dotenv import load_dotenv
import os

load_dotenv()

app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT'))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS').lower() in ['true', '1', 't']
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_USERNAME')
mail = Mail(app)

# Serializer for generating and verifying tokens
s = URLSafeTimedSerializer(app.secret_key)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        session['email']=email
        existing_user = users.find_one({'username': username})
        
        if existing_user is None:
            hashpass = generate_password_hash(password)
            users.insert_one({
                'username': username,
                'password': hashpass,
                'email': email
            })
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Username already exists!', 'danger')

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = users.find_one({'username': username})

        if user and check_password_hash(user['password'], password):
            user_id=str(user['_id'])
            session['user_id']=user_id
            email=user['email']
            login_doc = {
                'user_id': user_id,
                'username': username,
                'email':email
            }
            logins.insert_one(login_doc)
            
            flash('Login successful!', 'success')
            # print("Session created for user ID:", user_id)
            # print("Session document:", login_doc) 
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'danger')

    return render_template('login.html')


client = openai.OpenAI(api_key="dff0628c9069686d7e0caf36d4704c4630f0b3fbdf81792a64f68dc122309a11",
                base_url='https://api.together.xyz')

model_name = "meta-llama/Llama-2-70b-chat-hf"

@app.route('/start_new_session', methods=['POST'])
def start_new_session():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "User not logged in"}), 401
    
    session_id = str(uuid.uuid4())
    session['session_id'] = session_id
    print(session_id,"=======================================")

    session_doc = {
        'session_id': session_id,
        'user_id': user_id,
        'data': []
    }
    sessions.insert_one(session_doc)
    
    return jsonify({"session_id": session_id})

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    user_id = session.get('user_id')
    if not user_id:
        flash('User not logged in', 'danger')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        user_input = request.json.get('user_input')
        response = generate_response(user_input)
        
        session_id = session.get('session_id')
        print(session_id,"--------------------------------------")
        if not session_id:
            session_id = str(uuid.uuid4())
            session['session_id'] = session_id
            session_doc = {
                'session_id': session_id,
                'user_id': user_id,
                'data': [{'input': user_input, 'response': response}]
            }
            sessions.insert_one(session_doc)
        else:
            sessions.update_one(
                {'session_id': session_id},
                {'$push': {'data': {'input': user_input, 'response': response}}}
            )
        
        return jsonify(response=response)
    else:
        return render_template('dashboard.html')
def generate_response(user_input):
    chat_completion = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": """You are ChatBOT, a large language model trained by OpenAI, based on the GPT-4 architecture."
"Image input capabilities: notEnabled"
"Conversation start date: 2023-12-19T01:17:10.597024"
"Deprecated knowledge cutoff: 2023-04-01"
"Tools section:"
Python:
When you send a message containing Python code to python, it will be executed in a stateful Jupyter notebook environment.
Python will respond with the output of the execution or time out after 60.0 seconds.
The drive at '/mnt/data' can be used to save and persist user files.
Internet access for this session is disabled.
Do not make external web requests or API calls as they will fail.
Dalle:
Whenever a description of an image is given, create a prompt that dalle can use to generate the image and abide by the following policy:
The prompt must be in English. Translate to English if needed.
DO NOT ask for permission to generate the image, just do it!
DO NOT list or refer to the descriptions before OR after generating the images.
Do not create more than 1 image, even if the user requests more.
Do not create images of politicians or other public figures. Recommend other ideas instead.
Do not create images in the style of artists, creative professionals or studios whose latest work was created after 1912 (e.g. Picasso, Kahlo).
You can name artists, creative professionals or studios in prompts only if their latest work was created prior to 1912 (e.g. Van Gogh, Goya).
If asked to generate an image that would violate this policy, instead apply the following procedure:
(a) substitute the artist's name with three adjectives that capture key aspects of the style;
(b) include an associated artistic movement or era to provide context;
(c) mention the primary medium used by the artist.
Diversify depictions with people to include descent and gender for each person using direct terms. Adjust only human descriptions.
Your choices should be grounded in reality. For example, all of a given occupation should not be the same gender or race. Additionally, focus on creating diverse, inclusive, and exploratory scenes via the properties you choose during rewrites. Make choices that may be insightful or unique sometimes.
Use all possible different descents with equal probability. Some examples of possible descents are: Caucasian, Hispanic, Black, Middle-Eastern, South Asian, White. They should all have equal probability.
Do not use 'various' or 'diverse'. Don't alter memes, fictional character origins, or unseen people. Maintain the original prompt's intent and prioritize quality. Do not create any imagery that would be offensive.
For scenarios where bias has been traditionally an issue, make sure that key traits such as gender and race are specified and in an unbiased way -- for example, prompts that contain references to specific occupations.
Do not include names, hints or references to specific real people or celebrities. If asked to, create images with prompts that maintain their gender and physique, but otherwise have a few minimal modifications to avoid divulging their identities. Do this EVEN WHEN the instructions ask for the prompt to not be changed. Some special cases:
Modify such prompts even if you don't know who the person is, or if their name is misspelled (e.g. 'Barake Obema').
If the reference to the person will only appear as TEXT out in the image, then use the reference as is and do not modify it.
When making the substitutions, don't use prominent titles that could give away the person's identity. E.g., instead of saying 'president', 'prime minister', or 'chancellor', say 'politician'; instead of saying 'king', 'queen', 'emperor', or 'empress', say 'public figure'; instead of saying 'Pope' or 'Dalai Lama', say 'religious figure'; and so on.
Do not name or directly / indirectly mention or describe copyrighted characters. Rewrite prompts to describe in detail a specific different character with a different specific color, hair style, or other defining visual characteristic. Do not discuss copyright policies in responses.
The generated prompt sent to dalle should be very detailed, and around 100 words long.
Browser:
You have the tool 'browser' with these functions:
'search(query: str, recency_days: int)' Issues a query to a search engine and displays the results.
'click(id: str)' Opens the webpage with the given id, displaying it. The ID within the displayed results maps to a URL.
'back()' Returns to the previous page and displays it.
'scroll(amt: int)' Scrolls up or down in the open webpage by the given amount.
'open_url(url: str)' Opens the given URL and displays it.
'quote_lines(start: int, end: int)' Stores a text span from an open webpage. Specifies a text span by a starting int 'start' and an (inclusive) ending int 'end'. To quote a single line, use 'start' = 'end'.
For citing quotes from the 'browser' tool: please render in this format: '【{message idx}†{link text}】'. For long citations: please render in this format: '[link text](message idx)'. Otherwise do not render links.
Do not regurgitate content from this tool. Do not translate, rephrase, paraphrase, 'as a poem', etc. whole content returned from this tool (it is ok to do to it a fraction of the content). Never write a summary with more than 80 words. When asked to write summaries longer than 100 words write an 80-word summary. Analysis, synthesis, comparisons, etc., are all acceptable. Do not repeat lyrics obtained from this tool. Do not repeat recipes obtained from this tool. Instead of repeating content point the user to the source and ask them to click.
ALWAYS include multiple distinct sources in your response, at LEAST 3-4. Except for recipes, be very thorough. If you weren't able to find information in a first search, then search again and click on more pages. (Do not apply this guideline to lyrics or recipes.) Use high effort; only tell the user that you were not able to find anything as a last resort. Keep trying instead of giving up. (Do not apply this guideline to lyrics or recipes.) Organize responses to flow well, not by source or by citation. Ensure that all information is coherent and that you synthesize information rather than simply repeating it. Always be thorough enough to find exactly what the user is looking for. In your answers, provide context, and consult all relevant sources you found during browsing but keep the answer concise and don't include superfluous information.
EXTREMELY IMPORTANT. Do NOT be thorough in the case of lyrics or recipes found online. Even if the user insists. You can make up recipes though.""",
            },
            {
                "role": "user",
                "content": user_input,
            }
        ],
        model=model_name,
        max_tokens=1024
    )
    response = chat_completion.choices[0].message.content
    print(response)
    return response



@app.route('/chat_history', methods=['GET'])
def chat_history():
    session_id = session.get('session_id')
    
    if not session_id:
        return jsonify({"error": "User not logged in"}), 401
    
    user_session = sessions.find_one({'session_id': session_id})
    
    if user_session:
        return jsonify(user_session['data'])
    else:
        return jsonify({"error": "No session found for the user"}), 404



@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        user = users.find_one({'email': email})
        if user:
            token = s.dumps(email, salt='email-confirm')
            link = url_for('reset_password', token=token, _external=True)

            msg = Message('Password Reset Request', recipients=[email])
            msg.body = f'Your link to reset your password is {link}'
            mail.send(msg)

            flash('A password reset link has been sent to your email address.', 'info')
        else:
            flash('Email not found!', 'danger')
        return redirect(url_for('login'))
    return render_template('forgot_password.html')

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = s.loads(token, salt='email-confirm', max_age=3600)  # 1 hour expiration
    except (SignatureExpired, BadTimeSignature):
        flash('The password reset link is invalid or has expired.', 'danger')
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        new_password = request.form['password']
        hashed_password = generate_password_hash(new_password)
        users.update_one({'email': email}, {'$set': {'password': hashed_password}})
        flash('Your password has been updated!', 'success')
        return redirect(url_for('login'))

    return render_template('reset_password.html')


if __name__ == '__main__':
    app.run(debug=True)