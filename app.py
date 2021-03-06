import os
from flask import Flask, render_template, render_template, session, redirect, url_for, request, jsonify
from flask.ext.script import Manager, Shell
from flask.ext.bootstrap import Bootstrap
from flask.ext.wtf import Form
from wtforms import StringField, SubmitField, IntegerField
from wtforms.validators import Required
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.migrate import Migrate, MigrateCommand
from flask.ext.httpauth import HTTPBasicAuth, HTTPDigestAuth

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'reggie_magic_key'
app.config['SQLALCHEMY_DATABASE_URI'] =\
    'sqlite:///' + os.path.join(basedir, 'data.sqlite')
app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True
app.config['ADMIN_USERS'] = {
    'admin':'not_verybig_secret'
}


manager = Manager(app)
bootstrap = Bootstrap(app)
db = SQLAlchemy(app)
migrate = Migrate(app, db)
httpauth = HTTPDigestAuth()

@httpauth.get_password
def get_pw(username):
    if username in app.config['ADMIN_USERS']:
        return app.config['ADMIN_USERS'].get(username)
    return None

class Student(db.Model):
    __tablename__ = 'students'
    id = db.Column(db.Integer, primary_key=True)
    pod_number = db.Column(db.Integer, unique=True)
    username = db.Column(db.String(64))
    addr_wan = db.Column(db.String(16))

    def __init__(self):
        self.pod_number = self._next_pod()

    def addr_lo0(self):
        addr = "10.255.255.{0}/32".format(self.pod_number)
        return addr

    def addr_st0(self):
        addr = "10.255.{0}.2/30".format(self.pod_number)
        return addr

    def _next_pod(self):
        MAX_PODS = 255
        new_pod_id = 1
        pods = Student.query.order_by('pod_number').all()

        for pod in pods:
            # print "Pod: {0} / {1}".format(pod.username, pod.pod_number)
            if new_pod_id == pod.pod_number:
                # print "Found ID: {0}".format(pod.pod_number)
                pass
            else:
                # print "Unused: {0}".format(new_pod_id)
                if new_pod_id > MAX_PODS:
                    # print "Exceed Max Pods"
                    return False
                return new_pod_id
            
            new_pod_id = new_pod_id + 1

        if new_pod_id > MAX_PODS:
            # print "Exceed Max Pods Outer"
            return False
        else:
            # print new_pod_id
            return new_pod_id

    def to_json(self):
        json_student = {
            'url': url_for('get_student', pod_number=self.pod_number, _external=True),
            'id': self.id,
            'username': self.username,
            'pod_number': self.pod_number,
            'addr_wan': self.addr_wan,
            'addr_lo0': self.addr_lo0(),
            'addr_st0': self.addr_st0()
        }
        return json_student

    def __repr__(self):
        return '<Student {0} @ {1}>'.format(self.username, self.addr_wan)

class NameForm(Form):
    name = StringField('What is your name?', validators=[Required()])
    submit = SubmitField('Submit')

class PodForm(Form):
    username = StringField('What is your name?', validators=[Required()])
    pod_number = IntegerField('What is your pod number', validators=[Required()])
    addr_wan = StringField('What is your WAN Address?', validators=[Required()])
    submit = SubmitField('Submit')

@manager.command
def db_mock():
    '''
    Create some test database entries
    '''
    group =[
        {'username': 'Kurt', 'pod_number': 9},
        {'username': 'Rob', 'pod_number': 10},
        {'username': 'John', 'pod_number': 5},
        {'username': 'Erin', 'pod_number': 21}
    ]

    for i in group:
        s = Student()
        s.username = i['username']
        s.pod_number = i['pod_number'] # Force out of order pods
        db.session.add(s)
        db.session.commit()

    return True

@manager.command
def db_mock_solo():
    '''
    Create some test database entries
    '''
    group =[
        {'username': 'inital_user', 'pod_number': 1},
    ]

    for i in group:
        s = Student()
        s.username = i['username']
        s.pod_number = i['pod_number'] # Force out of order pods
        db.session.add(s)
        db.session.commit()

    return True

def make_shell_context():
    return dict(app=app, db=db, Student=Student)
manager.add_command("shell", Shell(make_context=make_shell_context))
manager.add_command('db', MigrateCommand)

@app.errorhandler(404)
def page_not_found(e):
    if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
        response = jsonify({'error': 'not found'})
        response.status_code = 404
        return response
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_server_error(e):
    if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
        response = jsonify({'error': 'Internal Server Error'})
        response.status_code = 500
        return response
    return render_template('500.html'), 500

@app.route('/', methods=['GET', 'POST'])
def index():
    name = None
    form = NameForm()
    if form.validate_on_submit():
        pod = Student()
        pod.username = form.name.data
        pod.addr_wan = request.remote_addr
        
        try:
            db.session.add(pod)
            db.session.commit()
        except:
            db.session.rollback()

        return redirect(url_for('get_student', pod_number=pod.pod_number))
    
    temp_pod = Student.query.filter_by(addr_wan=request.remote_addr).first()

    if temp_pod:
        return redirect(url_for('get_student', pod_number=temp_pod.pod_number))

    return render_template('index.html', form=form, name=name)

@app.route('/student/', methods=['GET', 'POST'])
def get_students():
    pods = Student.query.all()
    if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html and request.method == 'GET':
        return jsonify({ 'pods': [ pod.to_json() for pod in pods] })

    temp_pod = Student.query.filter_by(addr_wan=request.remote_addr).first()
    if temp_pod:
        return redirect(url_for('get_student', pod_number=temp_pod.pod_number))

    return redirect(url_for('index'))

@app.route('/student/<int:pod_number>', methods=['GET', 'POST'])
def get_student(pod_number):
    pod = Student.query.filter_by(pod_number=pod_number).first_or_404()

    if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html and request.method == 'GET':
        return jsonify(pod.to_json())

    if request.method == 'POST':
        temp_pod = Student.query.filter_by(id=request.form.get('id')).first_or_404()
        temp_pod.username = request.form.get('username')
        temp_pod.pod_number = request.form.get('pod_number')
        temp_pod.addr_wan = request.form.get('addr_wan')
        try:
            db.session.add(temp_pod)
            db.session.commit()
        except:
            db.session.rollback()
        return redirect(url_for('get_student', pod_number=temp_pod.pod_number))

    return render_template('student.html', username=pod.username, pod_number = pod.pod_number, addr_st0=pod.addr_st0(), addr_lo0=pod.addr_lo0(), addr_wan=pod.addr_wan, known=session.get('known', False))

#@app.route('/student/<int:pod_number>', methods=['DELETE'])
@app.route('/admin/delete/<int:pod_number>', methods=['POST'])
@httpauth.login_required
def delete_student(pod_number):
    #temp_pod = Student.query.filter_by(pod_number=pod_number).first_or_404()
    #db.session.delete(temp_pod)
    try:
        Student.query.filter_by(pod_number=pod_number).delete()
        db.session.commit()
    except:
        db.session.rollback()
    return redirect(url_for('admin'))
    #pass

@app.route('/admin/', methods=['GET', 'POST'])
@httpauth.login_required
def admin():
    post_dst = url_for('get_students')
    #del_dst = url_for('delete_student')
    pods = Student.query.order_by('pod_number').all()
    return render_template('admin.html', pods=pods, post_dst=post_dst, del_dst="/admin/delete/")

if __name__ == '__main__':
    manager.run()