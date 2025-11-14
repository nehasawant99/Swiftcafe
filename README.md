

#  **SwiftCafe – Café Website with Table Booking System**

SwiftCafe is a simple and modern café website built using **HTML, CSS (frontend)** and **Python + MySQL (backend)**.
The platform allows users to **view the café menu, explore special brews, and book tables** for regular visits, birthdays, parties, and time-slot based reservations.

---

##  **Features**

* Clean and responsive café website UI
* Menu showcase (coffee, snacks, drinks)
* Table booking system with time-slot selection
* Booking support for birthdays & small parties
* Backend built using Python
* MySQL database for managing bookings & users
* Simple and lightweight code structure

---

##  **Tech Stack**

**Frontend:**

* HTML
* CSS

**Backend:**

* Python (Flask / Django / Custom script)

**Database:**

* MySQL (with benchmarking for performance testing)

---

##  **Project Structure**

```
SwiftCafe/
│── static/
│   ├── css/
│   └── images/
│── templates/
│   ├── index.html
│   ├── menu.html
│   ├── booking.html
│── db/
│   └── swiftcafe.sql
│── app.py
│── README.md
```

---

##  **Database (MySQL)**

* Stores user bookings
* Stores time slots
* Stores party/birthday reservation details

---

##  **How to Run**

1. Install required Python packages:

   ```
   pip install flask mysql-connector-python
   ```
2. Import the `swiftcafe.sql` file into MySQL.
3. Run the backend:

   ```
   python app.py
   ```
4. Open in browser:

   ```
   http://localhost:5000
   ```

---

##  **Purpose of the Website**

To offer customers an easy way to **explore the menu**, **check special items**, and **book tables or event time slots** for parties and birthdays.



