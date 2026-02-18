from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3
from datetime import datetime
from sentence_transformers import SentenceTransformer
import joblib
from wordcloud import WordCloud
import matplotlib.pyplot as plt
import os

app = Flask(__name__)
app.secret_key = "secret123"

# Load Model
bert = SentenceTransformer('all-MiniLM-L6-v2')
model = joblib.load("hybrid_cyberbullying_model.pkl")

# DB Helper
def get_db():
    return sqlite3.connect("database.db")


# --------- AUTH SYSTEM ---------

@app.route('/')
def index():
    return redirect('/login')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        user = request.form['user']
        pw = request.form['pw']
        con = get_db()
        con.execute("INSERT INTO users(username,password) VALUES(?,?)",(user,pw))
        con.commit()
        con.close()
        return redirect('/login')
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        user = request.form['user']
        pw = request.form['pw']
        con = get_db()
        cur = con.execute("SELECT id FROM users WHERE username=? AND password=?",(user,pw))
        data = cur.fetchone()
        if data:
            session['uid'] = data[0]
            return redirect('/home')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


# --------- HOME ---------
@app.route('/home')
def home():
    if 'uid' not in session:
        return redirect('/login')
    return render_template('home.html')


# --------- PREDICTION ---------
@app.route('/predict', methods=['GET','POST'])
def predict():
    if 'uid' not in session:
        return redirect('/login')
    
    result = ""
    steps = ""
    if request.method == "POST":
        txt = request.form['text']
        X = bert.encode([txt])
        pred = model.predict(X)[0]
        prob = model.predict_proba(X)[0]
        label = "bullying" if pred == 0 else "notbullying"

        # Insert into DB
        con = get_db()
        con.execute("INSERT INTO history(uid,text,label,prob,time) VALUES(?,?,?,?,?)",
                    (session['uid'],txt,label,max(prob),str(datetime.now())))
        con.commit()

        if label == "bullying":
            steps = """✅ Do not respond immediately
✅ Block the offender
✅ Capture screenshots
✅ Report to platform
✅ Talk to trusted adults"""

        result = label.upper()

    return render_template('predict.html', result=result, steps=steps)


# --------- HISTORY ---------
@app.route('/history')
def history():
    if 'uid' not in session:
        return redirect('/login')
    con = get_db()
    cur = con.execute("SELECT text,label,prob,time FROM history WHERE uid=?",(session['uid'],))
    data = cur.fetchall()
    return render_template('history.html', data=data)


# --------- ANALYTICS ---------
@app.route('/analytics')
def analytics():
    if 'uid' not in session:
        return redirect('/login')

    con = get_db()
    cur1 = con.execute("SELECT COUNT(*) FROM history WHERE uid=? AND label='bullying'",(session['uid'],))
    b = cur1.fetchone()[0]

    cur2 = con.execute("SELECT COUNT(*) FROM history WHERE uid=? AND label='notbullying'",(session['uid'],))
    nb = cur2.fetchone()[0]

    # generate wordcloud
    cur3 = con.execute("SELECT text FROM history WHERE uid=?", (session['uid'],))
    txts = " ".join([t[0] for t in cur3.fetchall()])
    wc = WordCloud(width=500,height=300).generate(txts)
    wc.to_file("static/wordcloud.png")

    return render_template('analytics.html', b=b, nb=nb)


if __name__ == "__main__":
    # Create tables if not exists
    con = get_db()
    con.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, password TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS history(id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, text TEXT, label TEXT, prob TEXT, time TEXT)")
    con.commit()
    con.close()

    app.run(debug=True)
