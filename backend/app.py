# file: backend/app.py
import os
from flask import Flask, request, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_migrate import Migrate
from dotenv import load_dotenv
from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from PyPDF2 import PdfReader, PdfWriter
from twilio.rest import Client

load_dotenv()

app = Flask(__name__)
CORS(app)

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", "mysql+pymysql://root:@192.168.220.65/student_db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
migrate = Migrate(app, db)

TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_TOKEN = os.getenv("TWILIO_TOKEN")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM")
client = Client(TWILIO_SID, TWILIO_TOKEN)

class Student(db.Model):
    __tablename__ = 'students'
    id = db.Column(db.Integer, primary_key=True)
    admission_no = db.Column(db.String(10), unique=True, nullable=False)
    first_name = db.Column(db.String(64), nullable=False)
    middle_name = db.Column(db.String(64), nullable=False)
    family_name = db.Column(db.String(64))
    grade = db.Column(db.String(32), nullable=False)
    tuition_fee = db.Column(db.Integer, default=0)
    food_fee = db.Column(db.Integer, default=0)
    text_books_fee = db.Column(db.Integer, default=0)
    exercise_books_fee = db.Column(db.Integer, default=0)
    assesment_tool_fee = db.Column(db.Integer, default=0)
    transport_fee = db.Column(db.Integer, default=0)
    activity_fee = db.Column(db.Integer, default=200)
    diary_fee = db.Column(db.Integer, default=150)
    admission_fee = db.Column(db.Integer, default=0)
    total_fee = db.Column(db.Integer, default=0)
    amount_paid = db.Column(db.Integer, default=0)
    balance = db.Column(db.Integer, default=0)
    transport_mode = db.Column(db.String(32))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

def generate_admission_no():
    prefix = "AJA"
    last = db.session.query(Student).order_by(Student.id.desc()).first()
    next_idx = int(last.admission_no.replace(prefix, "")) + 1 if last else 1
    return f"{prefix}{next_idx:03d}"

@app.route('/api/students', methods=['POST'])
def add_student():
    data = request.get_json()
    for fld in ['first_name', 'middle_name', 'grade']:
        if not data.get(fld):
            return jsonify({'error': f'Missing field {fld}'}), 400

    admission_no = data.get('admission_no') or generate_admission_no()
    if Student.query.filter_by(admission_no=admission_no).first():
        return jsonify({'error': 'Admission number already exists'}), 400

    grade_fees = {"Playgroup":6500, "PP1":6500, "PP2":6500,
                  "Grade1":8500, "Grade2":8500, "Grade3":8500,
                  "Grade4":9000, "Grade5":9000, "Grade6":9000,
                  "Grade7":12000, "Grade8":12000, "Grade9":12000}
    transport_fees = {"None":0, "OneWay":4500, "TwoWayTown":7000, "TwoWayUma":8000}

    t = grade_fees.get(data['grade'], 0)
    f = 3500 if data.get('food') else 0
    tb = 6000 if data.get('text_books_fee') else 0
    eb = 500 if data.get('exercise_books_fee') else 0
    at = 300 if data.get('assesment_tool_fee') else 0
    tr = transport_fees.get(data.get('transport_mode', 'None'), 0)
    adm = 1000 if data['grade'] == 'Playgroup' else 0
    act, dia = 200, 150
    total = t + f + tb + eb + at + tr + act + dia + adm
    paid = int(data.get('amount_paid', 0))
    bal = total - paid

    student = Student(
        admission_no=admission_no, first_name=data['first_name'],
        middle_name=data['middle_name'], family_name=data.get('family_name'),
        grade=data['grade'], tuition_fee=t, food_fee=f, text_books_fee=tb,
        exercise_books_fee=eb, assesment_tool_fee=at, transport_fee=tr,
        admission_fee=adm, activity_fee=act, diary_fee=dia,
        total_fee=total, amount_paid=paid, balance=bal,
        transport_mode=data.get('transport_mode','None')
    )
    db.session.add(student)
    db.session.commit()
    return jsonify({'message':'Student added','admission_no':admission_no}), 201

@app.route('/api/students/<admission_no>/pdf', methods=['GET'])
def get_fee_pdf(admission_no):
    student = Student.query.filter_by(admission_no=admission_no).first_or_404()
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.drawString(50,750, f"Fee Statement: {student.admission_no}")
    c.drawString(50,730, f"Name: {student.first_name} {student.middle_name} {student.family_name or ''}")
    c.drawString(50,710, f"Grade: {student.grade}")
    y = 690
    for key in ['tuition', 'food', 'text_books', 'exercise_books', 'assesment_tool', 'transport', 'activity', 'diary', 'admission']:
        val = getattr(student, f"{key}_fee")
        c.drawString(50, y, f"{key.replace('_',' ').title()} Fee: Ksh {val}")
        y -= 20
    c.drawString(50, y, f"Total: Ksh {student.total_fee}")
    y -= 20; c.drawString(50, y, f"Paid: Ksh {student.amount_paid}")
    y -= 20; c.drawString(50, y, f"Balance: Ksh {student.balance}")
    c.save()
    buf.seek(0)

    reader = PdfReader(buf); writer = PdfWriter()
    for pg in reader.pages:
        writer.add_page(pg)
    writer.encrypt(user_pwd=student.admission_no)
    out = BytesIO(); writer.write(out); out.seek(0)

    return send_file(out,
                     as_attachment=True,
                     download_name=f"{admission_no}_fee.pdf",
                     mimetype="application/pdf")

@app.route('/api/students/<admission_no>/whatsapp', methods=['POST'])
def send_whatsapp(admission_no):
    data = request.get_json()
    if not data.get('to'):
        return jsonify({'error':'Missing "to" phone number'}), 400

    Student.query.filter_by(admission_no=admission_no).first_or_404()
    link = f"{request.host_url}api/students/{admission_no}/pdf"
    msg = client.messages.create(
        from_=TWILIO_WHATSAPP_FROM,
        body=f"Fee statement: {link}",
        to=data['to']
    )
    return jsonify({'sid': msg.sid}), 200

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
