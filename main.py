import random
from datetime import datetime, timedelta, date, time
from pydoc import html

from flask import Flask, render_template, request, redirect, flash, url_for, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
import json


app = Flask(__name__)

# Setting up MySQL database
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'local_healthdb'
app.secret_key = 'secret'  # Required for flash messages

mysql = mysql.connector.connect(
    host=app.config['MYSQL_HOST'],
    user=app.config['MYSQL_USER'],
    password=app.config['MYSQL_PASSWORD'],
    database=app.config['MYSQL_DB']
)
cursor = mysql.cursor(dictionary=True)


@app.route('/')
def index():
    if session.get('role') in ('patient', 'receptionist', 'doctor'):
        return "Welcome to Dashboard"
    else:
        return redirect(url_for('auth_login'))

@app.route('/index_doctor')
def index_doctor():
    try:
        # Check if user is logged in and has 'doctor' role
        if 'doctor_id' in session and 'role' in session and session['role'] == 'doctor':
            doctor_id = session['doctor_id']

            # Fetch doctor details from the database
            cursor.execute("SELECT name, contact_number, email, status FROM Doctors WHERE doctor_id = %s", (doctor_id,))
            doctor = cursor.fetchone()

            if doctor:
                return render_template('index_doctor.html', doctor=doctor)
            else:
                flash('Doctor not found', 'error')
                return redirect(url_for('index_doctor'))
        else:
            flash('You need to log in as a doctor to view this page', 'error')
            return redirect(url_for('auth_login'))  # Assuming there is a login page
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('index_doctor'))


@app.route('/reg_receptionists', methods=['GET', 'POST'])
def reg_receptionists():
    if request.method == 'POST':
        # Retrieve form data
        name = request.form.get('name')
        email = request.form.get('email')
        contact_number = request.form.get('contact_number')
        password = request.form.get('password')
        role = "receptionist"  # Set default role to receptionist

        # Input validation
        if not name or not email or not contact_number or not password:
            flash("All fields are required!", 'danger')
            return redirect(url_for('reg_receptionists'))

        # Check if email already exists
        cursor.execute("SELECT * FROM user WHERE email = %s", (email,))
        existing_user = cursor.fetchone()
        if existing_user:
            flash("Email is already registered!", 'danger')
            return redirect(url_for('reg_receptionists'))

        # Hash password
        hashed_password = generate_password_hash(password)

        try:
            # Insert the new receptionist into the users table
            cursor.execute("""
                INSERT INTO user (email, password, role) 
                VALUES (%s, %s, %s)
            """, (email, hashed_password, role))
            mysql.commit()

            # Get the user_id of the newly inserted user
            cursor.execute("SELECT user_id FROM user WHERE email = %s", (email,))
            user_id = cursor.fetchone()['user_id']

            # Insert into receptionists table with user_id as foreign key
            cursor.execute("""
                INSERT INTO Receptionists (name, contact_number, email, user_id) 
                VALUES (%s, %s, %s, %s)
            """, (name, contact_number, email, user_id))
            mysql.commit()

            flash("Receptionist registered successfully!", 'success')
            return redirect(url_for('index'))
        except Exception as e:
            mysql.rollback()  # Rollback on error
            flash(f"An error occurred: {str(e)}", 'danger')

    return render_template('reg_receptionists.html')


@app.route('/reg_doctor', methods=['GET', 'POST'])
def reg_doctor():
    # Fetch all departments from the database
    cursor.execute("SELECT * FROM departments")
    departments = cursor.fetchall()

    # Fetch specialties based on selected department
    specialties = []
    if request.method == 'POST':
        department_id = request.form.get('department')
        if department_id:
            cursor.execute("SELECT * FROM specialties WHERE department_id = %s", (department_id,))
            specialties = cursor.fetchall()

        # Handle doctor registration if form is submitted
        if request.method == 'POST' and request.form.get('name') and request.form.get('email') and request.form.get('contact_number') and request.form.get('password') and request.form.get('specialty'):
            # Get form data
            name = request.form.get('name')
            email = request.form.get('email')
            contact_number = request.form.get('contact_number')
            password = request.form.get('password')
            specialty_id = request.form.get('specialty')
            department_id = request.form.get('department')

            # Input validation
            if not name or not email or not contact_number or not password or not specialty_id or not department_id:
                flash("All fields are required!", 'danger')
                return redirect(url_for('reg_doctor'))

            # Check if email already exists
            cursor.execute("SELECT * FROM user WHERE email = %s", (email,))
            existing_user = cursor.fetchone()
            if existing_user:
                flash("Email is already registered!", 'danger')
                return redirect(url_for('reg_doctor'))

            # Hash password
            hashed_password = generate_password_hash(password)

            try:
                # Insert the new user
                cursor.execute("""INSERT INTO user (email, password, role) VALUES (%s, %s, 'doctor')""", (email, hashed_password))
                mysql.commit()

                # Get user_id
                cursor.execute("SELECT user_id FROM user WHERE email = %s", (email,))
                user_id = cursor.fetchone()['user_id']

                # Insert doctor with specialty_id and department_id as foreign keys
                cursor.execute("""
                    INSERT INTO doctors (name, contact_number, email, user_id, specialty_id, department_id) 
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (name, contact_number, email, user_id, specialty_id, department_id))
                mysql.commit()

                flash("Doctor registered successfully!", 'success')
                return redirect(url_for('reg_doctor'))

            except Exception as e:
                mysql.rollback()  # Rollback on error
                flash(f"An error occurred: {str(e)}", 'danger')

    return render_template('reg_doctor.html', departments=departments, specialties=specialties)


@app.route('/get_specialties', methods=['GET'])
def get_specialties():
    department_id = request.args.get('department_id')

    if department_id:
        # Fetch specialties for the selected department
        cursor.execute("SELECT specialty_id, specialty_name FROM specialties WHERE department_id = %s",
                       (department_id,))
        specialties = cursor.fetchall()

        # Prepare the result to send back as JSON
        specialty_list = [{"specialty_id": spec["specialty_id"], "specialty_name": spec["specialty_name"]} for spec in
                          specialties]
        return jsonify(specialty_list)
    return jsonify([])  # Return an empty list if no department_id is provided


@app.route('/reg_patient', methods=['GET', 'POST'])
def reg_patient():
    if request.method == 'POST':
        # Retrieve form data
        name = request.form.get('name')
        email = request.form.get('email')
        contact_number = request.form.get('contact_number')
        date_of_birth = request.form.get('date_of_birth')
        address = request.form.get('address')
        password = request.form.get('password')
        role = "patient"
        date_registered = date.today()

        # Input validation
        if not all([name, email, contact_number, date_of_birth, password]):
            flash("All required fields must be filled!", 'danger')
            return redirect(url_for('reg_patient'))

        # Check if email already exists in User table
        cursor.execute("SELECT * FROM User WHERE email = %s", (email,))
        existing_user = cursor.fetchone()
        if existing_user:
            flash("Email is already registered!", 'danger')
            return redirect(url_for('reg_patient'))

        # Fetch available doctors who haven’t been assigned
        cursor.execute("""
            SELECT doctor_id FROM Doctors 
            WHERE doctor_id NOT IN (SELECT doctor_id FROM AssignedDoctors)
            AND status = 'active'
        """)
        available_doctors = cursor.fetchall()

        # If no doctors are available, reset the AssignedDoctors table
        if not available_doctors:
            cursor.execute("DELETE FROM AssignedDoctors")
            mysql.commit()
            cursor.execute("""
                SELECT doctor_id FROM Doctors WHERE status = 'active'
            """)
            available_doctors = cursor.fetchall()

        # Pick a random doctor from available doctors
        assigned_doctor = random.choice(available_doctors)['doctor_id']

        # Hash password
        hashed_password = generate_password_hash(password)

        try:
            # Insert into User table
            cursor.execute("""
                INSERT INTO User (email, password, role) 
                VALUES (%s, %s, %s)
            """, (email, hashed_password, role))
            mysql.commit()

            # Get user_id of newly created user
            cursor.execute("SELECT user_id FROM User WHERE email = %s", (email,))
            user_id = cursor.fetchone()['user_id']

            # Insert into Patients table
            cursor.execute("""
                INSERT INTO Patients (name, date_of_birth, address, contact_number, registered_doctor_id, date_registered, users_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (name, date_of_birth, address, contact_number, assigned_doctor, date_registered, user_id))
            mysql.commit()

            # Mark the doctor as assigned by adding to AssignedDoctors
            cursor.execute("INSERT INTO AssignedDoctors (doctor_id) VALUES (%s)", (assigned_doctor,))
            mysql.commit()

            flash("Patient registered successfully with assigned doctor!", 'success')
            return redirect(url_for('reg_patient'))
        except Exception as e:
            mysql.rollback()
            flash(f"An error occurred: {str(e)}", 'danger')

    return render_template('reg_patient.html')


@app.route('/auth_login', methods=['GET', 'POST'])
def auth_login():
    if request.method == 'POST':
        email = request.form.get('email-username')
        password = request.form.get('password')

        if not email or not password:
            flash("Please fill in both fields!", 'danger')
            return redirect(url_for('auth_login'))

        try:
            # Fetch user details based on the email only
            cursor.execute("SELECT * FROM user WHERE email = %s", (email,))
            user = cursor.fetchone()

            # Check if user exists and password matches
            if user and check_password_hash(user['password'], password):
                # Save session data based on role
                session['user_id'] = user['user_id']
                session['role'] = user['role']

                # Redirect based on the user's role
                if user['role'] == 'patient':
                    # Fetch patient_id for the logged-in user
                    cursor.execute("SELECT patient_id FROM patients WHERE users_id = %s", (user['user_id'],))
                    patient = cursor.fetchone()
                    session['patient_id'] = patient['patient_id'] if patient else None
                    return redirect(url_for('patient_dashboard'))

                elif user['role'] == 'doctor':
                    # Fetch doctor_id for the logged-in user
                    cursor.execute("SELECT doctor_id FROM doctors WHERE user_id = %s", (user['user_id'],))
                    doctor = cursor.fetchone()
                    session['doctor_id'] = doctor['doctor_id'] if doctor else None
                    return redirect(url_for('index_doctor'))

                elif user['role'] == 'receptionist':
                    # Fetch receptionist_id for the logged-in user
                    cursor.execute("SELECT receptionist_id FROM receptionists WHERE user_id = %s", (user['user_id'],))
                    receptionist = cursor.fetchone()
                    session['receptionist_id'] = receptionist['receptionist_id'] if receptionist else None
                    return redirect(url_for('appointments'))

            else:
                flash("Invalid email/username or password", 'danger')
                return redirect(url_for('auth_login'))
        except Exception as e:
            flash(f"An error occurred: {str(e)}", 'danger')
            return redirect(url_for('auth_login'))

    return render_template('auth_login.html')


# Dashboard routes (for demonstration purposes)
@app.route('/patient_dashboard')
def patient_dashboard():
    if session.get('role') == 'patient':
        return "Welcome to Patient Dashboard"
    else:
        return redirect(url_for('auth_login'))


@app.route('/doctor_dashboard')
def doctor_dashboard():
    if session.get('role') == 'doctor':
        return "Welcome to doctor Dashboard"
    else:
        return redirect(url_for('auth_login'))


@app.route('/receptionist_dashboard')
def receptionist_dashboard():
    if session.get('role') == 'receptionist':
        return  redirect(url_for('header.html'))
    else:
        return redirect(url_for('auth_login'))


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('role', None)
    session.pop('patient_id', None)
    session.pop('doctor_id', None)
    session.pop('receptionist_id', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('auth_login'))

@app.route('/doctor_schedule', methods=['GET', 'POST'])
def doctor_schedule():
    # Check if doctor is logged in
    if 'doctor_id' not in session:
        flash('You need to log in as a doctor first.', 'danger')
        return redirect(url_for('auth_login'))  # Assuming you have a login route

    if request.method == 'POST':
        doctor_id = session['doctor_id']
        schedule_data = request.form.get('schedule_data')

        if schedule_data:
            # Parse the JSON string into a Python list
            try:
                schedule_list = json.loads(schedule_data)

                # Insert the schedule into the database
                for schedule in schedule_list:
                    cursor.execute("""
                        INSERT INTO Doctor_Schedule (doctor_id, AvailableDate, AvailableFrom, AvailableTo)
                        VALUES (%s, %s, %s, %s)
                    """, (doctor_id, schedule['availableDate'], schedule['availableFrom'], schedule['availableTo']))
                mysql.commit()
                flash('Schedule successfully submitted!', 'success')
            except Exception as e:
                mysql.rollback()
                flash(f'Error: {str(e)}', 'danger')
        else:
            flash('No schedule data submitted.', 'danger')

    return render_template('doctor_schedule.html')

# Route to display patient form
@app.route('/book_appointment', methods=['GET', 'POST'])
def book_appointment():
    if request.method == 'POST':
        patient_id = request.form.get('patient_id')
        session['patient_id'] = patient_id
        # Check if patient exists
        cursor.execute("SELECT name, registered_doctor_id FROM Patients WHERE patient_id = %s", (patient_id,))
        patient = cursor.fetchone()
        if patient:
            session['patient_name'] = patient['name']
            session['registered_doctor_id'] = patient['registered_doctor_id']
            return redirect('/select_doctor')
        else:
            flash("Patient ID not found", "danger")
    return render_template('booking_appointment.html')

# Route to select doctor
@app.route('/select_doctor', methods=['GET', 'POST'])
def select_doctor():
    if 'registered_doctor_id' in session:
        doctor_id = session['registered_doctor_id']
        cursor.execute("SELECT name FROM Doctors WHERE doctor_id = %s", (doctor_id,))
        doctor = cursor.fetchone()
        if doctor:
            doctor_name = doctor['name']
        else:
            doctor_name = "No Doctor Assigned"
    else:
        doctor_name = "No Doctor Assigned"
    # Fetch all available doctors for reassignment if needed
    cursor.execute("SELECT doctor_id, name FROM Doctors WHERE status = 'active'")
    doctors = cursor.fetchall()
    return render_template('select_doctor.html', doctor_name=doctor_name, doctors=doctors)

# Route to show doctor availability
@app.route('/doctor_availability', methods=['GET', 'POST'])
def doctor_availability():
    # Get the selected doctor ID from the form or session
    selected_doctor_id = request.form.get('doctor_id', session['registered_doctor_id'])

    # Get doctor schedule with availability
    cursor.execute("""
        SELECT AvailableDate, AvailableFrom, AvailableTo
        FROM Doctor_Schedule
        WHERE doctor_id = %s AND AvailableDate >= CURDATE()
    """, (selected_doctor_id,))
    availability = cursor.fetchall()

    # Store the selected doctor ID in the session for later use in selecting a timeslot
    session['selected_doctor_id'] = selected_doctor_id

    return render_template('doctor_availability.html', availability=availability)


# Route to book appointment time slot
@app.route('/select_timeslot', methods=['POST'])
def select_timeslot():
    appointment_date = request.form.get('appointment_date')
    doctor_id = session.get('selected_doctor_id', session['registered_doctor_id'])

    # Query the doctor’s schedule on the selected date
    cursor.execute("""
        SELECT AvailableFrom, AvailableTo
        FROM Doctor_Schedule
        WHERE doctor_id = %s AND AvailableDate = %s
    """, (doctor_id, appointment_date))
    schedule = cursor.fetchone()

    if not schedule:
        flash("No available times for this date.", "danger")
        return redirect('/doctor_availability')

    # Check if AvailableFrom and AvailableTo are timedelta objects
    if isinstance(schedule['AvailableFrom'], timedelta) and isinstance(schedule['AvailableTo'], timedelta):
        available_from = (datetime.combine(datetime.strptime(appointment_date, "%Y-%m-%d"), time.min) + schedule[
            'AvailableFrom']).time()
        available_to = (datetime.combine(datetime.strptime(appointment_date, "%Y-%m-%d"), time.min) + schedule[
            'AvailableTo']).time()
    else:
        # If they're strings, convert them directly to time objects
        available_from = schedule['AvailableFrom']
        available_to = schedule['AvailableTo']

    # Now, combine the date with available times and generate timeslots
    available_start_datetime = datetime.combine(datetime.strptime(appointment_date, "%Y-%m-%d"), available_from)
    available_end_datetime = datetime.combine(datetime.strptime(appointment_date, "%Y-%m-%d"), available_to)

    # Generate 30-minute timeslots
    timeslots = []
    while available_start_datetime < available_end_datetime:
        timeslot_end = available_start_datetime + timedelta(minutes=30)
        timeslots.append((available_start_datetime.time(), timeslot_end.time()))
        available_start_datetime = timeslot_end

    return render_template('select_timeslot.html', timeslots=timeslots)


# Route to confirm booking
@app.route('/confirm_booking', methods=['POST'])
def confirm_booking():
    try:
        # Retrieve appointment details from the form and session
        selected_time = request.form.get('selected_time')
        appointment_date = request.form.get('appointment_date')
        doctor_id = session.get('selected_doctor_id', session['registered_doctor_id'])
        receptionist_id = session.get('receptionist_id')
        patient_id = session.get('patient_id')

        # Check for missing data
        if not (selected_time and appointment_date and doctor_id and patient_id):
            flash("Missing appointment details. Please try again.", "danger")
            return redirect('/book_appointment')

        # Save appointment in the database
        cursor.execute("""
            INSERT INTO Appointments (patient_id, doctor_id, receptionist_id, appointment_date, appointment_time)
            VALUES (%s, %s, %s, %s, %s)
        """, (patient_id, doctor_id, receptionist_id, appointment_date, selected_time))
        mysql.commit()

        # Fetch doctor and patient details for confirmation display
        cursor.execute("SELECT name FROM Doctors WHERE doctor_id = %s", (doctor_id,))
        doctor = cursor.fetchone()

        cursor.execute("SELECT name FROM Patients WHERE patient_id = %s", (patient_id,))
        patient = cursor.fetchone()

        # Check if doctor and patient details were retrieved
        if doctor is None or patient is None:
            flash("Doctor or patient details not found. Please try again.", "danger")
            return redirect('/book_appointment')

        # Store appointment details in the session for confirmation display
        session['appointment_details'] = {
            "doctor_name": doctor['name'],
            "patient_name": patient['name'],
            "appointment_date": appointment_date,
            "appointment_time": selected_time
        }

        flash("Appointment successfully booked.", "success")
        return redirect('/appointment_successful')

    except mysql.connector.Error as err:
        # Handle database errors
        flash(f"An error occurred: {err}", "danger")
        return redirect('/book_appointment')

@app.route('/appointment_successful')
def appointment_successful():
    # Retrieve appointment details from the session
    appointment_details = session.get('appointment_details')
    if not appointment_details:
        flash("No appointment details found.", "danger")
        return redirect('/book_appointment')

    # Render the appointment_successful page with the appointment details
    return render_template('appointment_successful.html', appointment_details=appointment_details)


@app.route('/appointments', methods=['GET', 'POST'])
def list_appointments():
    try:
        # Filters for searching
        search_patient = request.args.get('search_patient', '')
        search_doctor = request.args.get('search_doctor', '')
        search_date = request.args.get('search_date', '')
        search_time = request.args.get('search_time', '')

        # SQL query with search filters
        query = """
            SELECT A.appointment_id, P.name AS patient_name, D.name AS doctor_name, 
                   A.appointment_date, A.appointment_time, A.status
            FROM Appointments A
            JOIN Patients P ON A.patient_id = P.patient_id
            JOIN Doctors D ON A.doctor_id = D.doctor_id
            WHERE A.status = 'booked'
            AND (P.name LIKE %s OR %s = '')
            AND (D.name LIKE %s OR %s = '')
            AND (A.appointment_date = %s OR %s = '')
            AND (A.appointment_time = %s OR %s = '')
            ORDER BY A.appointment_date DESC, A.appointment_time DESC
        """
        cursor.execute(query, (
            f"%{search_patient}%", search_patient,
            f"%{search_doctor}%", search_doctor,
            search_date, search_date,
            search_time, search_time
        ))
        appointments = cursor.fetchall()

    except mysql.connector.Error as e:
        flash("An error occurred while fetching the appointments.", "error")
        appointments = []

    return render_template('list_of_appointment.html', appointments=appointments)


@app.route('/cancel_appointment', methods=['POST'])
def cancel_appointment():
    try:
        appointment_id = request.form['appointment_id']
        cancel_reason = request.form['cancel_reason']

        # Update the status and reason in the database
        query = """
            UPDATE Appointments 
            SET status = 'cancelled', cancel_reason = %s 
            WHERE appointment_id = %s
        """
        cursor.execute(query, (cancel_reason, appointment_id))
        mysql.commit()

        return jsonify({'success': True, 'message': 'Appointment cancelled successfully!'})
    except mysql.connector.Error as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/view_cancellations', methods=['GET'])
def view_cancellations():
    try:
        # Filters for searching
        search_patient = request.args.get('search_patient', '')
        search_doctor = request.args.get('search_doctor', '')
        search_date = request.args.get('search_date', '')
        search_time = request.args.get('search_time', '')

        # SQL query with search filters
        query = """
               SELECT A.appointment_id, P.name AS patient_name, D.name AS doctor_name, 
                      A.appointment_date, A.appointment_time, A.status, A.cancel_reason
               FROM Appointments A
               JOIN Patients P ON A.patient_id = P.patient_id
               JOIN Doctors D ON A.doctor_id = D.doctor_id
               WHERE A.status = 'cancelled'
               AND (P.name LIKE %s OR %s = '')
               AND (D.name LIKE %s OR %s = '')
               AND (A.appointment_date = %s OR %s = '')
               AND (A.appointment_time = %s OR %s = '')
               ORDER BY A.appointment_date DESC, A.appointment_time DESC
           """
        cursor.execute(query, (
            f"%{search_patient}%", search_patient,
            f"%{search_doctor}%", search_doctor,
            search_date, search_date,
            search_time, search_time
        ))
        view_cancellations = cursor.fetchall()

    except mysql.connector.Error as e:
        flash("An error occurred while fetching the appointments.", "error")
        view_cancellations = []

    return render_template('view_cancellations.html', cancellations=view_cancellations)

@app.route('/list_of_patient')
def list_of_patient():
    try:
        query = "SELECT patient_id, name, contact_number, status FROM Patients"
        cursor.execute(query)
        patients = cursor.fetchall()
        return render_template('list_of_patient.html', patients=patients)
    except Exception as e:
        flash(f"Error: {e}", "danger")
        return redirect(url_for('list_of_patient'))


# Patient Prescription
@app.route('/patient_prescription/<int:patient_id>', methods=['GET', 'POST'])
def patient_prescription(patient_id):
    try:
        if request.method == 'POST':
            # Add new prescription
            doctor_id = session.get('doctor_id')
            medication_details = html.escape(request.form['medication_details'])
            dosage = html.escape(request.form['dosage'])
            date_issued = request.form['date_issued']

            query = """
                INSERT INTO Prescriptions (patient_id, doctor_id, medication_details, dosage, date_issued)
                VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(query, (patient_id, doctor_id, medication_details, dosage, date_issued))
            mysql.commit()
            flash("Prescription added successfully!", "success")

        # Fetch existing prescriptions
        query = """
            SELECT prescription_id, medication_details, dosage, date_issued
            FROM Prescriptions
            WHERE patient_id = %s
        """
        cursor.execute(query, (patient_id,))
        prescriptions = cursor.fetchall()

        return render_template('patient_prescription.html', prescriptions=prescriptions, patient_id=patient_id)
    except Exception as e:
        flash(f"Error: {e}", "danger")
        return redirect(url_for('list_of_patient'))



if __name__ == '__main__':
    app.run(debug=True)