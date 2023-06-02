from flask import Flask, flash, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import docker

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///containerdb.sqlite"
app.config["SECRET_KEY"] = "crdftvgbhjnkmtrcdtfvgbyhnrctfvgbyhnj"
db = SQLAlchemy(app)
client = docker.from_env()


class Container(db.Model):
    id = db.Column(db.String(255), primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    image = db.Column(db.String(255), nullable=False)

    def __init__(self, id, name, image):
        self.id = id
        self.name = name
        self.image = image

    @property
    def status(self):
        try:
            container = client.containers.get(self.id)
        except:
            return 'not found'
        return container.status
    
    def calculate_billing(self):
        start_time = Billing.query.filter_by(container_id=self.id).order_by(Billing.start_time.desc()).first()
        if start_time:
            diff = datetime.now() - start_time.start_time
            seconds = diff.total_seconds()
            billing_amount = seconds * 1
            return billing_amount
        return 0


class Billing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    container_id = db.Column(db.String(255), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    stop_time = db.Column(db.DateTime, nullable=False)

    def __init__(self, container_id, start_time, stop_time):
        self.container_id = container_id
        self.start_time = start_time
        self.stop_time = stop_time


@app.route('/')
def index():
    containers = Container.query.all()
    return render_template("index.html", containers=containers)


@app.route('/create_container', methods=["GET", "POST"])
def create_container():
    if request.method == 'POST':
        name = request.form['name']
        image = request.form['image']
        docker_container = client.containers.run(image, detach=True)
        container = Container(docker_container.id, name, image)
        db.session.add(container)
        db.session.commit()
        flash(f'Container Done!! (id = {docker_container.id})')
    return render_template("create_container.html")


@app.route('/start_container/<container_id>')
def start_container(container_id):
    container = Container.query.filter_by(id=container_id).first_or_404()
    docker_container = client.containers.get(container_id)
    docker_container.start()
    flash('Successfully started container')
    return redirect(url_for('index'))


@app.route('/stop_container/<container_id>')
def stop_container(container_id):
    container = Container.query.filter_by(id=container_id).first_or_404()
    docker_container = client.containers.get(container_id)
    docker_container.stop()
    flash('Successfully stopped container')

    # Tambahkan entri billing
    billing = Billing(container_id=container_id, start_time=datetime.now(), stop_time=datetime.now())
    db.session.add(billing)
    db.session.commit()

    return redirect(url_for('index'))

@app.route('/delete_container/<container_id>')
def delete_container(container_id):
    container = Container.query.filter_by(id=container_id).first_or_404()
    try:
        docker_container = client.containers.get(container_id)
        docker_container.remove(force=True)
    except:
        pass
    db.session.delete(container)
    db.session.commit()
    flash('Successfully deleted container')
    return redirect(url_for('index'))


@app.route('/billing/<container_id>')
def billing(container_id):
    container = Container.query.filter_by(id=container_id).first()
    return render_template("billing.html", container=container)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=1025, debug=True)