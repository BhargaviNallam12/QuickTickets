from flask import Flask, render_template, request, redirect, session, send_file
import sqlite3
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Image, Table, TableStyle, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
import qrcode

app = Flask(__name__)
app.secret_key = "secret123"

# DATABASE
conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

# TABLES
cursor.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)")

cursor.execute("""
CREATE TABLE IF NOT EXISTS bookings (
    username TEXT,
    movie TEXT,
    seat TEXT,
    UNIQUE(movie, seat)
)
""")

cursor.execute("CREATE TABLE IF NOT EXISTS movies (name TEXT, image TEXT)")
conn.commit()

# INSERT MOVIES
cursor.execute("SELECT COUNT(*) FROM movies")
if cursor.fetchone()[0] == 0:
    movies = [
        ("RRR","rrr.png"), ("KGF Chapter 2","kgf.png"),
        ("Pushpa","pushpa.png"), ("Bahubali","bahubali.png"),
        ("Jawan","jawan.png"), ("Pathaan","pathaan.png"),
        ("Leo","leo.png"), ("Vikram","vikram.png"),
        ("Salaar","salaar.png"), ("Master","master.png"),
        ("Sarkaru Vaari Paata","svp.png"), ("Ala Vaikunthapurramuloo","ala.png")
    ]
    cursor.executemany("INSERT INTO movies VALUES (?,?)", movies)
    conn.commit()


# HOME
@app.route('/', methods=['GET','POST'])
def home():
    if 'user' not in session:
        return redirect('/login')

    search = ""

    if request.method == 'POST':
        search = request.form.get('search', '').strip()

        cursor.execute(
            "SELECT * FROM movies WHERE LOWER(name) LIKE ?",
            ('%' + search.lower() + '%',)
        )
    else:
        cursor.execute("SELECT * FROM movies")

    movies = cursor.fetchall()

    cursor.execute("SELECT * FROM movies")
    all_movies = cursor.fetchall()

    return render_template(
        "index.html",
        movies=movies,
        no_result=(len(movies) == 0),
        search=search.lower(),
        all_movies=all_movies
    )


# SIGNUP
@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method == 'POST':
        u = request.form['username'].strip()
        p = request.form['password'].strip()

        cursor.execute("SELECT * FROM users WHERE username=?", (u,))
        if cursor.fetchone():
            return "User already exists ❌"

        cursor.execute("INSERT INTO users VALUES (?,?)", (u,p))
        conn.commit()
        return redirect('/login')

    return render_template('signup.html')


# LOGIN
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        u = request.form['username'].strip()
        p = request.form['password'].strip()

        cursor.execute("SELECT * FROM users WHERE username=?", (u,))
        user = cursor.fetchone()

        if user and user[1] == p:
            session['user'] = u
            return redirect('/')
        else:
            return "Invalid login ❌"

    return render_template('login.html')


# LOGOUT
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


# FORGOT PASSWORD
@app.route('/forgot', methods=['GET','POST'])
def forgot():
    if request.method == 'POST':
        u = request.form['username'].strip()
        p = request.form['password'].strip()

        cursor.execute("SELECT * FROM users WHERE username=?", (u,))
        if cursor.fetchone():
            cursor.execute("UPDATE users SET password=? WHERE username=?", (p,u))
            conn.commit()
            return "Password updated! ✅ <br><a href='/login'>Go to Login</a>"
        else:
            return "User not found ❌"

    return render_template('forgot.html')


# BOOK PAGE
@app.route('/book/<movie>')
def book(movie):
    if 'user' not in session:
        return redirect('/login')

    cursor.execute("SELECT seat FROM bookings WHERE movie=?", (movie,))
    booked = [i[0] for i in cursor.fetchall()]

    cursor.execute("SELECT image FROM movies WHERE name=?", (movie,))
    data = cursor.fetchone()
    img = data[0] if data else "default.png"

    return render_template('book.html', movie=movie, image=img, booked_seats=booked)


# SUMMARY (AJAX)
@app.route('/summary', methods=['POST'])
def summary():
    data = request.get_json()

    session['seats'] = data.get('seats', [])
    session['movie'] = data.get('movie', '')
    session['total'] = data.get('total', 0)

    return "/summary_page"


@app.route('/summary_page')
def summary_page():
    if 'seats' not in session or len(session['seats']) == 0:
        return redirect('/')

    return render_template("summary.html",
        movie=session['movie'],
        seats=session['seats'],
        total=session['total']
    )


# PAYMENT
@app.route('/payment')
def payment():
    total = request.args.get('total')

    if not total:
        return redirect('/')

    return render_template('payment.html', total=total)


# CONFIRM BOOKING
@app.route('/confirm_booking')
def confirm_booking():

    if 'user' not in session or 'seats' not in session:
        return redirect('/')

    user = session['user']
    movie = session['movie']
    seats = session['seats']

    for s in seats:
        cursor.execute("SELECT * FROM bookings WHERE movie=? AND seat=?", (movie, s))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO bookings VALUES (?,?,?)", (user, movie, s))

    conn.commit()

    return redirect('/history')


# DOWNLOAD TICKET
@app.route('/download_ticket')
def download_ticket():

    file_path = "ticket.pdf"
    doc = SimpleDocTemplate(file_path, pagesize=letter)
    styles = getSampleStyleSheet()

    movie = session.get('movie', '')
    seats = ', '.join(session.get('seats', []))
    total = session.get('total', 0)

    content = []

    header = Table([["🎬 QuickTickets"]], colWidths=[450])
    header.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f84464")),
        ('TEXTCOLOR', (0,0), (-1,-1), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER')
    ]))

    content.append(header)
    content.append(Spacer(1, 20))

    details = [
        ["Movie:", movie],
        ["Seats:", seats],
        ["Total:", f"₹{total}"],   # ✅ FIXED
        ["Status:", "Confirmed ✅"]
    ]

    table = Table(details)
    content.append(table)
    content.append(Spacer(1, 20))

    qr = qrcode.make(f"{movie} | {seats} | ₹{total}")
    qr.save("qr.png")

    content.append(Image("qr.png", width=120, height=120))

    doc.build(content)

    return send_file(file_path, as_attachment=True)


# HISTORY
@app.route('/history')
def history():
    if 'user' not in session:
        return redirect('/login')

    user = session['user']
    cursor.execute("SELECT movie, seat FROM bookings WHERE username=?", (user,))
    data = cursor.fetchall()

    return render_template('history.html', bookings=data)


# RUN
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
