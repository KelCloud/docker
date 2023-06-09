from flask import Flask, flash, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import docker
import threading
from threading import Timer

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///containerdb.sqlite"
app.config["SECRET_KEY"] = "crdftvgbhjnkmtrcdtfvgbyhnrctfvgbyhnj"
db = SQLAlchemy(app)
client = docker.from_env()


class Container(db.Model):
    id = db.Column(db.String(255), primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    image = db.Column(db.String(255), nullable=False)
    port = db.Column(db.String(255), nullable=False)
    

    def __init__(self, id, name, image, port):
        self.id = id
        self.name = name
        self.image = image
        self.port = port

    @property
    def status(self):
        try:
            container = client.containers.get(self.id)
        except:
            return 'not found'
        return container.status

    def calculate_billing(self):
        # Check if the container is running
        container_status = self.status
        if container_status == 'running':
            latest_billing = Billing.query.filter_by(container_id=self.id).order_by(Billing.start_time.desc()).first()
            if latest_billing:
                diff = datetime.now() - latest_billing.start_time
                seconds = diff.total_seconds()
                if seconds >= 0:
                    self.billing_amount = int(seconds) * 1
                    return self.billing_amount
        elif container_status == 'exited':
            total_billing = 0
            billings = Billing.query.filter_by(container_id=self.id).all()
            for billing in billings:
                diff = billing.stop_time - billing.start_time
                seconds = diff.total_seconds()
                billing_amount = int(seconds) * 1
                total_billing += billing_amount
                self.total_billing=total_billing
                self.billing_amount=billing_amount
            return self.total_billing,self.billing_amount
        return 0



class Billing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    container_id = db.Column(db.String(255), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    stop_time = db.Column(db.DateTime, nullable=True)

    def __init__(self, container_id, start_time, stop_time=None):
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
        port = request.form['port']  # Retrieve the port value from the form

        # Start the container with the specified port
        docker_container = client.containers.run(image, detach=True, ports={'80/tcp': port})

        # Create a Container object and save it in the database
        container = Container(docker_container.id, name, image, port)
        db.session.add(container)
        billing = Billing(container_id=container.id, start_time=datetime.now(), stop_time=None)
        db.session.add(billing)
        db.session.commit()
        flash(f'Container Done!! (id = {docker_container.id})')

    return render_template("create_container.html")

@app.route('/start_container/<container_id>')
def start_container(container_id):
    container = Container.query.filter_by(id=container_id).first_or_404()
    docker_container = client.containers.get(container_id)
    docker_container.start()
    flash('Successfully started container')
    billing = Billing(container_id=container_id, start_time=datetime.now(), stop_time=None)
    db.session.add(billing)
    db.session.commit()

    return redirect(url_for('index'))


@app.route('/stop_container/<container_id>')
def stop_container(container_id):
    container = Container.query.filter_by(id=container_id).first_or_404()
    docker_container = client.containers.get(container_id)
    docker_container.stop()
    flash('Successfully stopped container')

    billing = Billing.query.filter_by(container_id=container_id, stop_time=None).first()
    if billing:
        billing.stop_time = datetime.now()
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


@app.route('/schedule_container', methods=["GET", "POST"])
def schedule_container():
    if request.method == 'POST':
        name = request.form['name']
        image = request.form['image']
        port = request.form['port']
        start_time = datetime.strptime(request.form['start_time'], "%Y-%m-%dT%H:%M")
        stop_time = datetime.strptime(request.form['stop_time'], "%Y-%m-%dT%H:%M")

        docker_container = client.containers.run(image, detach=True, name=name, ports={'80/tcp': port})
        container = Container(docker_container.id, name, image, port)
        container.start_time = start_time  # Menyimpan waktu start dalam objek kontainer
        db.session.add(container)
        db.session.commit()
        flash(f'Container Scheduled and Started!! (name = {name})')

        # Hitung selisih waktu antara sekarang dan waktu stop
        time_difference = (stop_time - datetime.now()).total_seconds()

        # Buat timer untuk menghentikan kontainer sesuai waktu stop yang diinput
        timer = Timer(time_difference, stop_scheduled_container, args=[docker_container.id])
        timer.start()

        billing = Billing(container_id=container.id, start_time=start_time, stop_time=None)
        billing.billing_amount = 0
        db.session.add(billing)
        db.session.commit()

        return redirect(url_for('index'))

    return render_template("schedule.html")


def stop_scheduled_container(container_id):
    container = Container.query.filter_by(id=container_id).first()
    docker_container = client.containers.get(container_id)
    docker_container.stop()
    flash('Successfully stopped scheduled container')

    # Tambahkan entri billing
    billing = Billing.query.filter_by(container_id=container_id, stop_time=None).first()
    if billing:
        billing.stop_time = datetime.now()
        db.session.commit()

    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=1025, debug=True)