from flask import Flask,redirect,url_for,render_template,request,flash,abort,session,send_file
from flask_session import Session
from key import secret_key,salt1,salt2
import flask_excel as excel
from stoken import token
from cmail import sendmail
from itsdangerous import URLSafeTimedSerializer
import mysql.connector
from io import BytesIO
import os
app=Flask(__name__)
app.secret_key=secret_key
app.config['SESSION_TYPE']='filesystem'
Session(app)
excel.init_excel(app)
#mydb=mysql.connector.connect(host='localhost',user='root',password='admin',db='prm')
db= os.environ['RDS_DB_NAME']
user=os.environ['RDS_USERNAME']
password=os.environ['RDS_PASSWORD']
host=os.environ['RDS_HOSTNAME']
port=os.environ['RDS_PORT']
with mysql.connector.connect(host=host,user=user,password=password,db=db) as conn:
    cursor=conn.cursor(buffered=True)
    cursor.execute('create table if not exists users(username varchar(15) primary key,password varchar(15),email varchar(80),email_status enum("confirmed","not confirmed"))')
    cursor.execute('create table if not exists notes(nid BINARY(16) PRIMARY KEY,title TINYTEXT,content TEXT,date TIMESTAMP DEFAULT CURRENT_TIMESTAMP on update current_timestamp,added_by VARCHAR(15),FOREIGN KEY (added_by) REFERENCES users(username))')
    cursor.execute('create table if not exists files(fid binary(16) primary key,extension varchar(8),filedata longblob,date timestamp default now() on update now(),added_by varchar(15), FOREIGN KEY (added_by) REFERENCES users(username))')
mydb=mysql.connector.connect(host=host,user=user,password=password,db=db)
@app.route('/')
def index():
    return render_template('title.html')
@app.route('/login',methods=['GET','POST'])
def login():
    if session.get('user'):
        return redirect(url_for('home'))
    if request.method=='POST':
        username=request.form['username']
        password=request.form['password']
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select count(*) from users where username=%s',[username])
        count=cursor.fetchone()[0]
        if count==1:
            cursor.execute('select count(*) from users where username=%s and password=%s',[username,password])
            p_count=cursor.fetchone()[0]
            if p_count==1:
                session['user']=username
                cursor.execute('select email_status from users where username=%s',[username])
                status=cursor.fetchone()[0]
                cursor.close()
                if status!='confirmed':
                    return redirect(url_for('inactive'))
                else:
                    return redirect(url_for('home'))
            else:
                cursor.close()
                flash('invalid password')
                return render_template('login.html')
        else:
            cursor.close()
            flash('invalid username')
            return render_template('login.html')
    return render_template('login.html')
@app.route('/inactive')
def inactive():
    if session.get('user'):
        username=session.get('user')
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select email_status from users where username=%s',[username])
        status=cursor.fetchone()[0]
        cursor.close()
        if status=='confirmed':
            return redirect(url_for('home'))
        else:
            return render_template('inactive.html')
    else:
        return redirect(url_for('login'))
@app.route('/homepage',methods=['GET','POST'])
def home():
    if session.get('user'):
        username=session.get('user')
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select email_status from users where username=%s',[username])
        status=cursor.fetchone()[0]
        cursor.close()
        if status=='confirmed':
            if request.method=='POST':
                result=f"%{request.form['search']}%"
                cursor=mydb.cursor(buffered=True)
                cursor.execute("select bin_to_uuid(nid) as uid,title,date from notes where  title like %s  and added_by=%s",[result,username])
                data=cursor.fetchall()
                if len(data)==0:
                    data='empty'
                return render_template('table.html',data=data)
            return render_template('homepage.html')
        else:
            return redirect(url_for('inactive'))
    else:
        return redirect(url_for('login'))
@app.route('/resendconfirmation')
def resend():
    if session.get('user'):
        username=session.get('user')
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select email_status from users where username=%s',[username])
        status=cursor.fetchone()[0]
        cursor.execute('select email from users where username=%s',[username])
        email=cursor.fetchone()[0]
        cursor.close()
        if status=='confirmed':
            flash('Email already confirmed')
            return redirect(url_for('home'))
        else:
            subject='Email Confirmation'
            confirm_link=url_for('confirm',token=token(email,salt1),_external=True)
            body=f"Please confirm your mail-\n\n{confirm_link}"
            sendmail(to=email,body=body,subject=subject)
            flash('Confirmation link sent check your email')
            return redirect(url_for('inactive'))
    else:
        return redirect(url_for('login'))
@app.route('/registration',methods=['GET','POST'])
def registration():
    if request.method=='POST':
        username=request.form['username']
        password=request.form['password']
        email=request.form['email']
        cursor=mydb.cursor(buffered=True)
        try:
            cursor.execute('insert into users (username,password,email) values(%s,%s,%s)',(username,password,email))
        except mysql.connector.IntegrityError:
            flash('Username or email is already in use')
            return render_template('registration.html')
        else:
            mydb.commit()
            cursor.close()
            subject='Email Confirmation'
            confirm_link=url_for('confirm',token=token(email,salt1),_external=True)
            body=f"Thanks for signing up.Follow this link-\n\n{confirm_link}"
            sendmail(to=email,body=body,subject=subject)
            flash('Confirmation link sent check your email')
            return render_template('registration.html')
    return render_template('registration.html')
    
@app.route('/confirm/<token>')
def confirm(token):
    try:
        serializer=URLSafeTimedSerializer(secret_key)
        email=serializer.loads(token,salt=salt1,max_age=120)
    except Exception as e:
        #print(e)
        abort(404,'Link expired')
    else:
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select email_status from users where email=%s',[email])
        status=cursor.fetchone()[0]
        cursor.close()
        if status=='confirmed':
            flash('Email already confirmed')
            return redirect(url_for('login'))
        else:
            cursor=mydb.cursor(buffered=True)
            cursor.execute("update users set email_status='confirmed' where email=%s",[email])
            mydb.commit()
            flash('Email confirmation success')
            return redirect(url_for('login'))
@app.route('/forget',methods=['GET','POST'])
def forgot():
    if request.method=='POST':
        email=request.form['email']
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select count(*) from users where email=%s',[email])
        count=cursor.fetchone()[0]
        cursor.close()
        if count==1:
            cursor=mydb.cursor(buffered=True)
            cursor.execute('SELECT email_status from users where email=%s',[email])
            status=cursor.fetchone()[0]
            cursor.close()
            if status!='confirmed':
                flash('Please Confirm your email first')
                return render_template('forgot.html')
            else:
                subject='Forget Password'
                confirm_link=url_for('reset',token=token(email,salt=salt2),_external=True)
                body=f"Use this link to reset your password-\n\n{confirm_link}"
                sendmail(to=email,body=body,subject=subject)
                flash('Reset link sent check your email')
                return redirect(url_for('login'))
        else:
            flash('Invalid email id')
            return render_template('forgot.html')
    return render_template('forgot.html')
@app.route('/reset/<token>',methods=['GET','POST'])
def reset(token):
    try:
        serializer=URLSafeTimedSerializer(secret_key)
        email=serializer.loads(token,salt=salt2,max_age=180)
    except:
        abort(404,'Link Expired')
    else:
        if request.method=='POST':
            newpassword=request.form['npassword']
            confirmpassword=request.form['cpassword']
            if newpassword==confirmpassword:
                cursor=mydb.cursor(buffered=True)
                cursor.execute('update users set password=%s where email=%s',[newpassword,email])
                mydb.commit()
                flash('Reset Successful')
                return redirect(url_for('login'))
            else:
                flash('Passwords mismatched')
                return render_template('newpassword.html')
        return render_template('newpassword.html')

@app.route('/logout')
def logout():
    if session.get('user'):
        session.pop('user')
        return redirect(url_for('login'))
    else:
        return redirect(url_for('login'))

@app.route('/addnotes',methods=['POST','GET'])
def addnotes():
    if session.get('user'):
        if request.method=='POST':
            title=request.form['title']
            content=request.form['content']
            username=session.get('user')
            cursor=mydb.cursor(buffered=True)
            cursor.execute('insert into notes (nid,title,content,added_by) values(UUID_TO_BIN(UUID()),%s,%s,%s)',[title,content,username])
            mydb.commit()
            cursor.close()
            flash('Notes added successfully')
            return redirect(url_for('viewnotes'))
        return render_template('addnotes.html')
    else:
        return redirect(url_for('login'))
@app.route('/viewnotes')
def viewnotes():
    if session.get('user'):
        username=session.get('user')
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select bin_to_uuid(nid) as uid,title,date from notes where added_by=%s order by date desc',[username])
        data=cursor.fetchall()
        cursor.close()
        return render_template('table.html',data=data)
    else:
        return redirect(url_for('login'))
@app.route('/nid/<uid>')
def vnid(uid):
    if session.get('user'):
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select bin_to_uuid(nid),title,content,date from notes where bin_to_uuid(nid)=%s',[uid])
        cursor.close()
        uid,title,content,date=cursor.fetchone()
        return render_template('viewnotes.html',title=title,content=content,date=date)
    else:
        return redirect(url_for('login'))
@app.route('/delete/<uid>')
def delete(uid):
    if session.get('user'):
        cursor=mydb.cursor(buffered=True)
        cursor.execute('delete from notes where bin_to_uuid(nid)=%s',[uid])
        mydb.commit()
        cursor.close()
        flash('notes deleted successfully')
        return redirect(url_for('viewnotes'))
    else:
        return redirect(url_for('login'))

@app.route('/update/<uid>',methods=['GET','POST'])
def update(uid):
    if session.get('user'):
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select bin_to_uuid(nid),title,content from notes where bin_to_uuid(nid)=%s',[uid])
        uid,title,content =cursor.fetchone()
        cursor.close()
        if request.method=='POST':
            title=request.form['title']
            content=request.form['content']
            cursor=mydb.cursor(buffered=True)
            cursor.execute('update notes set title=%s,content=%s where bin_to_uuid(nid)=%s',[title,content,uid])
            mydb.commit()
            cursor.close()
            flash('notes upated successfully')
            return redirect(url_for('viewnotes'))
        return render_template('update.html',title=title,content=content)
    else:
        return redirect(url_for('login'))
@app.route('/fileupload',methods=['GET','POST'])
def fileupload():
    if session.get('user'):
        if request.method=='POST':
            files=request.files.getlist('file')
            username=session.get('user')
            cursor=mydb.cursor(buffered=True)
            for file in files: 
                file_ext=file.filename.split('.')[-1]
                file_data=file.read()#reads binary data from file
                cursor.execute('insert into files(fid,extension,filedata,added_by) values(uuid_to_bin(uuid()),%s,%s,%s)',[file_ext,file_data,username])
                mydb.commit()
            cursor.close()
            flash('files uploded successfully')
            return redirect(url_for('filesview'))
        return render_template('fileupload.html')
    else:
        return redirect(url_for('login'))
@app.route('/filesview')
def filesview():
    if session.get('user'):
        username=session.get('user')
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select bin_to_uuid(fid) as uid,date from files where added_by=%s order by date desc',[username])
        data=cursor.fetchall()
        return render_template('fileview.html',data=data)
    else:
        return redirect(url_for('login'))
@app.route('/viewfid/<uid>')
def viewfid(uid):
    if session.get('user'):
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select extension,filedata from files where bin_to_uuid(fid)=%s',[uid])
        ext,bin_data=cursor.fetchone()
        bytes_data=BytesIO(bin_data)
        filename=f'attachement.{ext}'
        return send_file(bytes_data,download_name=filename,as_attachment=False)
    else:
        return redirect(url_for('login'))
@app.route('/download/<uid>')
def download(uid):
    if session.get('user'):
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select extension,filedata from files where bin_to_uuid(fid)=%s',[uid])
        ext,bin_data=cursor.fetchone()
        bytes_data=BytesIO(bin_data)
        filename=f'attachement.{ext}'
        return send_file(bytes_data,download_name=filename,as_attachment=True)
    else:
        return redirect(url_for('login'))
@app.route('/filedelete/<uid>')
def filedelete(uid):
    if session.get('user'):
        cursor=mydb.cursor(buffered=True)
        cursor.execute('delete from files where bin_to_uuid(fid)=%s',[uid])
        mydb.commit()
        cursor.close()
        flash('file deleted successfully')
        return redirect(url_for('filesview'))
    else:
        return redirect(url_for('login'))
@app.route('/getnotesdata')
def getdata():
    if session.get('user'):
        username=session.get('user')
        cursor=mydb.cursor(buffered=True)
        columns=['Title','Content','Date']
        cursor.execute('select title,content,date from notes where added_by=%s',[username])
        data=cursor.fetchall()
        array_data=[list(i) for i in data]
        array_data.insert(0,columns)
        return excel.make_response_from_array(array_data,'xlsx',filename='notesdata')
    else:
        return redirect(url_for('login'))
if __name__=='__main__':
    app.run()