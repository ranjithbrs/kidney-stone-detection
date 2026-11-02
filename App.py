from flask import Flask, render_template, flash, request, session, send_file
from flask import render_template, redirect, url_for, request
import pandas as pd
import sys
import numpy as np
import mysql.connector
import pickle


app = Flask(__name__)
app.config.from_object(__name__)
app.config['SECRET_KEY'] = '7d441f27d441f27567d441f2b6176a'


@app.route("/")
def homepage():
    return render_template('index.html')


#================================Admin===============================


@app.route("/AdminLogin")
def AdminLogin():
    return render_template('AdminLogin.html')


@app.route("/adminlogin", methods=['GET', 'POST'])
def adminlogin():
    if request.method == 'POST':
        if request.form['uname'] == 'admin' and request.form['pas'] == 'admin':
            conn = mysql.connector.connect(user='root', password='', host='localhost', database='1kidneystoneyolodb')
            cur = conn.cursor()
            cur.execute("SELECT * FROM regtb ")
            data = cur.fetchall()
            flash("Your are Logged In...!")
            return render_template('AdminHome.html', data=data)
        else:
            flash("Username or Password is wrong")
            return render_template('AdminLogin.html')


@app.route("/AdminHome")
def AdminHome():
    conn = mysql.connector.connect(user='root', password='', host='localhost', database='1kidneystoneyolodb')
    cur = conn.cursor()
    cur.execute("SELECT * FROM regtb")
    data = cur.fetchall()
    return render_template('AdminHome.html', data=data)


#==========================================User======================================


@app.route("/NewUser")
def NewUser():
    return render_template('NewUser.html')


@app.route("/newuser", methods=['GET', 'POST'])
def newuser():
    if request.method == 'POST':

        name = request.form['name']
        gender= request.form['gender']
        age = request.form['age']
        email = request.form['email']
        mobile = request.form['mobile']
        address = request.form['address']
        uname = request.form['uname']
        pas = request.form['pas']

        conn = mysql.connector.connect(user='root', password='', host='localhost', database='1kidneystoneyolodb')
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO regtb VALUES ('','" + name + "','" + gender + "','" + age + "','" + email + "'"
                                        ",'" + mobile + "','" + address + "','" + uname + "','" + pas + "')")
        conn.commit()
        conn.close()
        flash('New User Registered successfully')
        conn = mysql.connector.connect(user='root', password='', host='localhost', database='1kidneystoneyolodb')
        cur = conn.cursor()
        cur.execute("SELECT * FROM regtb ")
        data = cur.fetchall()

        return render_template('UserLogin.html',data=data)


@app.route("/UserLogin")
def UserLogin():
    return render_template('UserLogin.html')


@app.route("/userlogin", methods=['GET', 'POST'])
def userlogin():
    if request.method == 'POST':
        uname = request.form['uname']
        pas = request.form['pas']
        session['uname'] = request.form['uname']

        conn = mysql.connector.connect(user='root', password='', host='localhost', database='1kidneystoneyolodb')
        cursor = conn.cursor()
        cursor.execute("SELECT * from regtb where UserName='" + uname + "' and password='" + pas + "'")
        data = cursor.fetchone()
        if data is None:
            flash("UserName or Password is wrong...!")
            return render_template('UserLogin.html')
        else:
            session['email'] = data[4]
            session['mob'] = data[5]
            session['add'] = data[6]

            conn = mysql.connector.connect(user='root', password='', host='localhost', database='1kidneystoneyolodb')
            cur = conn.cursor()
            cur.execute("SELECT * FROM regtb where UserName='" + uname + "' and password='" + pas + "'")
            data = cur.fetchall()
            flash("Your are Logged In...!")

            return render_template('UserHome.html', data=data)


@app.route("/UserHome")
def UserHome():
    uname = session['uname']
    conn = mysql.connector.connect(user='root', password='', host='localhost', database='1kidneystoneyolodb')
    cur = conn.cursor()
    cur.execute("SELECT * FROM regtb where UserName='" + uname + "'")
    data = cur.fetchall()
    return render_template('UserHome.html',data=data)


#=======================================SendMail===========================================


def sendmail(message):
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.base import MIMEBase
    from email import encoders

    fromaddr = "projectmailm@gmail.com"
    toaddr = session['email']

    # instance of MIMEMultipart
    msg = MIMEMultipart()

    # storing the senders email address
    msg['From'] = fromaddr

    # storing the receivers email address
    msg['To'] = toaddr

    # storing the subject
    msg['Subject'] = "Cattle Disease Detection"

    # string to store the body of the mail
    body = message

    # attach the body with the msg instance
    msg.attach(MIMEText(body, 'plain'))

    # open the file to be sent
    filename = "alert.jpg"
    attachment = open("alert.jpg", "rb")

    # instance of MIMEBase and named as p
    p = MIMEBase('application', 'octet-stream')

    # To change the payload into encoded form
    p.set_payload((attachment).read())

    # encode into base64
    encoders.encode_base64(p)

    p.add_header('Content-Disposition', "attachment; filename= %s" % filename)

    # attach the instance 'p' to instance 'msg'
    msg.attach(p)

    # creates SMTP session
    s = smtplib.SMTP('smtp.gmail.com', 587)

    # start TLS for security
    s.starttls()

    # Authentication
    s.login(fromaddr, "tdyr kebi hnyr yzyh")

    # Converts the Multipart msg into a string
    text = msg.as_string()

    # sending the mail
    s.sendmail(fromaddr, toaddr, text)

    # terminating the session
    s.quit()



if __name__ == '__main__':
    app.run(
        host='0.0.0.0',   # Allow connections from other devices
        port=5000,
        debug=True,
        use_reloader=True
    )


