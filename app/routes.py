from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import check_password_hash, generate_password_hash
from flask import make_response
from flask import render_template_string
from flask import make_response, render_template, request
from . import mysql, login_manager
from datetime import datetime
import pandas as pd
from flask import send_file
import io
from xhtml2pdf import pisa
import MySQLdb.cursors
import pdfkit
import platform
import os


path_wkhtmltopdf = '/usr/bin/wkhtmltopdf'
if not os.path.exists(path_wkhtmltopdf):
    raise RuntimeError(f"wkhtmltopdf tidak ditemukan di {path_wkhtmltopdf}")
config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)


main = Blueprint("main", __name__)

class User(UserMixin):
    def __init__(self, id, username, password_hash, role):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cur.fetchone()
    if user:
        return User(*user)
    return None

@main.route("/")
def index():
    return redirect(url_for("main.login"))

@main.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        if user and check_password_hash(user[2], password):
            user_obj = User(*user)
            login_user(user_obj)
            return redirect(url_for("main.dashboard"))
        else:
            flash("Invalid credentials", "danger")
            return redirect(url_for("main.login"))
        print("User dari DB:", user)

    return render_template("login.html")


@main.route("/users")
@login_required
def list_users():
    if current_user.role != 'admin':
        flash("Akses ditolak", "danger")
        return redirect(url_for("main.dashboard"))

    cur = mysql.connection.cursor()
    cur.execute("SELECT id, username, role FROM users")
    users = cur.fetchall()
    return render_template("users/list.html", users=users)

@main.route("/users/add", methods=["GET", "POST"])
@login_required
def add_user():
    if current_user.role != 'admin':
        flash("Akses ditolak", "danger")
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        role = request.form["role"]

        password_hash = generate_password_hash(password)
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
                    (username, password_hash, role))
        mysql.connection.commit()
        flash("User berhasil ditambahkan", "success")
        return redirect(url_for("main.list_users"))

    return render_template("users/add.html")


@main.route("/dashboard")
@login_required
def dashboard():
    print("Role:", current_user.role)  # debug print
    return render_template("dashboard.html", name=current_user.username)



# ------------------------
# CRUD Produk
# ------------------------

@main.route("/products")
@login_required
def list_products():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT id, code, name, category, purchase_price, price, stock_in, stock_sold
        FROM products
    """)
    products = cur.fetchall()
    return render_template("products/list.html", products=products)


@main.route("/products/list")
@login_required
def export_product():
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT code, name, category, stock_in, stock_sold, stock_live
        FROM products
    """)
    stok = cur.fetchall()
    df_stok = pd.DataFrame(stok, columns=["code", "name", "category", "stock_in", "stock_sold", "stock_live"])

    # Buat Excel dengan dua sheet
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_stok.to_excel(writer, sheet_name="stok_produk", index=False)

    output.seek(0)
    return send_file(output, download_name="laporan_transaksi.xlsx", as_attachment=True)

@main.route("/products/add", methods=["GET", "POST"])
@login_required
def add_product():
    if request.method == "POST":
        code = request.form["code"]
        name = request.form["name"]
        category = request.form["category"]
        purchase_price = float(request.form["purchase_price"])
        price = float(request.form["price"])
        stock_in = int(request.form["stock_in"])
        stock_sold = int(request.form["stock_sold"])
        
        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO products (code, name, category, purchase_price, price, stock_in, stock_sold)
            VALUES (%s, %s, %s, %s, %s, %s, %s )
        """,(code, name, category, purchase_price, price, stock_in, 0))
        mysql.connection.commit()
        flash("Produk berhasil ditambahkan", "success")
        return redirect(url_for("main.list_products"))
    
    return render_template("products/add.html")


@main.route("/products/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_product(id):
    cur = mysql.connection.cursor()

    if request.method == "POST":
        code            = request.form["code"].strip()
        name            = request.form["name"].strip()
        category        = request.form["category"].strip()
        purchase_price  = float(request.form["purchase_price"])
        price           = float(request.form["price"])
        stock_in        = int(request.form["stock_in"])
        stock_sold      = int(request.form["stock_sold"])
        stock_live      = stock_in - stock_sold

        # ► urutan tuple = urutan kolom di query
        cur.execute("""
            UPDATE products
            SET code=%s,
                name=%s,
                category=%s,
                purchase_price=%s,
                price=%s,
                stock_in=%s,
                stock_sold=%s,
                stock_live=%s
            WHERE id=%s
        """, (code, name, category,
              purchase_price,
              price, stock_in, stock_sold, stock_live, id))   # id di akhir
        mysql.connection.commit()

        flash("Produk berhasil diperbarui", "success")
        return redirect(url_for("main.list_products"))

    # GET – ambil data produk untuk form
    cur.execute("SELECT * FROM products WHERE id=%s", (id,))
    product = cur.fetchone()
    return render_template("products/edit.html", product=product)


@main.route("/products/delete/<int:id>")
@login_required
def delete_product(id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM products WHERE id=%s", (id,))
    mysql.connection.commit()
    flash("Produk berhasil dihapus", "danger")
    return redirect(url_for("main.list_products"))


# ------------------------
# TRANSAKSI PEMBELIAN
# ------------------------


@main.route("/purchases")
@login_required
def purchases():
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT id, name FROM products")
    products = cur.fetchall()
    return render_template("purchases/add.html", products=products)

@main.route("/purchases/add", methods=["POST"])
@login_required
def add_purchase():
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    if request.method == "POST":
        product_name = request.form["product_name"].strip()
        quantity = int(request.form["quantity"])
        try:
            purchase_price = float(request.form["purchase_price"])
        except ValueError:
            flash("Harga pembelian tidak valid", "danger")
            return redirect(url_for("main.purchases"))

        # Cek apakah produk sudah ada
        cur.execute("SELECT id FROM products WHERE name = %s", (product_name,))
        product = cur.fetchone()

        if product:
            product_id = product["id"]
        else:
            # Jika produk belum ada, tambahkan
            cur.execute("INSERT INTO products (name, stock_in) VALUES (%s, 0)", (product_name,))
            product_id = cur.lastrowid

        # Tambah ke tabel purchases
        cur.execute("INSERT INTO purchases (product_id, quantity, purchase_price) VALUES (%s, %s, %s)", (product_id, quantity, purchase_price))
        
        # Update stok produk
        cur.execute("UPDATE products SET stock_in = stock_in + %s WHERE id = %s", (quantity, product_id))

        cur.execute("""
            UPDATE products
            SET
                code            = COALESCE(code, %s),
                category        = COALESCE(category, %s),
                purchase_price  = CASE WHEN purchase_price = 0 THEN %s ELSE purchase_price END,
                price           = CASE WHEN price = 0 THEN %s ELSE price END
            WHERE id = %s
        """,(
            request.form.get("code") or None,
            request.form.get("category") or None,
            purchase_price,
            request.form.get("sell_price") or 0,
            product_id
        ))

        mysql.connection.commit()
        flash("Pembelian berhasil disimpan dan stok diperbarui", "success")
        return redirect(url_for("main.purchases"))

@main.route("/purchases/list")
@login_required
def list_purchases():
    cur = mysql.connection.cursor()
    query = """
        SELECT 
            p.id, pr.name, p.quantity, p.purchase_price, 
            (p.quantity * p.purchase_price) AS total_price,
            p.created_at
        FROM purchases p
        JOIN products pr ON p.product_id = pr.id
        ORDER BY p.created_at DESC
    """
    cur.execute(query)
    purchases = cur.fetchall()
    print("purchases", purchases)
    return render_template("purchases/list.html", purchases=purchases)




# ------------------------
# TRANSAKSI PENJUALAN
# ------------------------
@main.route("/sales")
@login_required
def sales():
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT id, name, price FROM products")
    products = cur.fetchall()
    print("Rendering: sales/add.html")  # Debugging
    return render_template("sales/add.html", products=products)

@main.route("/sales/add", methods=["POST"])
@login_required
def add_sale():
    cur = mysql.connection.cursor()

    customer = request.form.get("customer") or None
    cash = request.form.get("cash") or 0
    cash = float(cash)
    product_ids = request.form.getlist("product_id[]")
    qtys        = request.form.getlist("qty[]")
    prices      = request.form.getlist("price[]")

    # 0. Validasi panjang list sama
    if not (len(product_ids)==len(qtys)==len(prices)):
        flash("Input item tidak lengkap", "danger")
        return redirect(url_for('main.sales'))

    grand_total = 0
    items_data  = []

    # 1. Cek stok & hitung total
    for pid, q, p in zip(product_ids, qtys, prices):
        pid = int(pid); q=int(q); p=float(p)
        cur.execute("SELECT stock_in - stock_sold FROM products WHERE id=%s",(pid,))
        live = cur.fetchone()[0]
        if q > live:
            flash("Stok produk tidak cukup!", "danger")
            return redirect(url_for('main.sales'))
        items_data.append((pid, q, p, q*p))
        grand_total += q*p

    # 2. Insert header
    cur.execute("INSERT INTO sales (customer, grand_total) VALUES (%s,%s)", (customer, grand_total))
    sale_id = cur.lastrowid

    # 3. Insert items & update stok
    for pid, q, price, total in items_data:
        cur.execute("""INSERT INTO sale_items 
                       (sale_id, product_id, quantity, sell_price)
                       VALUES (%s,%s,%s,%s)""",
                    (sale_id, pid, q, price))
        cur.execute("UPDATE products SET stock_sold = stock_sold + %s WHERE id=%s", (q, pid))

    mysql.connection.commit()
    #flash("Penjualan disimpan", "success")
    return redirect(url_for('main.sales_invoice', sale_id=sale_id, cash=cash))


@main.route("/sales/list")
@login_required
def list_sales():
    cur = mysql.connection.cursor()
    query = """
        SELECT *
        FROM sale_items si JOIN products pr ON si.sale_id = pr.id
    """
    try:
        cur.execute(query)
        sales = cur.fetchall()
    except Exception as e:
        flash(f"Database error: {e}", "danger")
        return render_template("sales/list.html", sales=[])
    return render_template("sales/list.html", sales=sales)


# -------- tampil invoice HTML ----------
@main.route("/sales/invoice/<int:sale_id>")
@login_required
def sales_invoice(sale_id):
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cur.execute("SELECT * FROM sales WHERE id=%s", (sale_id,))
    sale = cur.fetchone()

    cur.execute("""SELECT si.*, p.name, p.code
                   FROM sale_items si
                   JOIN products p ON si.product_id=p.id
                   WHERE si.sale_id=%s""", (sale_id,))
    items = cur.fetchall()

    return render_template("sales/invoice.html", sale=sale, items=items)


# -------- download PDF ----------
@main.route("/sales/invoice/<int:sale_id>/pdf")
@login_required
def sales_invoice_pdf(sale_id):
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Ambil data header penjualan
    cur.execute("""
        SELECT s.id, s.sale_date, s.customer
        FROM sales s
        WHERE s.id = %s
    """, (sale_id,))
    sale = cur.fetchone()

    if not sale:
        flash("Invoice tidak ditemukan", "danger")
        return redirect(url_for('main.sales_history'))

    # Ambil detail produk yang dibeli
    cur.execute("""
        SELECT p.code, p.name, si.quantity, si.sell_price, si.total
        FROM sale_items si
        JOIN products p ON si.product_id = p.id
        WHERE si.sale_id = %s
    """, (sale_id,))
    items = cur.fetchall()

    # Hitung grand total
    grand_total = sum(item['total'] for item in items)

    # Kirim ke template PDF
    html = render_template("sales/invoice_pdf.html", sale=sale, items=items, grand_total=grand_total)
    options = {'enable-local-file-access': None}
    pdf = pdfkit.from_string(html, False, configuration=config, options=options)

    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=invoice_{sale_id}.pdf'
    return response





# ------------------------
# report
# ------------------------

@main.route("/report")
@login_required
def report():
    cur = mysql.connection.cursor()

    # Ambil pembelian
    cur.execute("""
        SELECT pr.name, p.quantity, (p.purchase_price*p.quantity) AS total_price, p.purchase_date
        FROM purchases p
        JOIN products pr ON p.product_id = pr.id
        ORDER BY p.purchase_date DESC
    """)
    purchases = cur.fetchall()

    # Ambil penjualan
    cur.execute("""
        SELECT
            p.name,
            si.quantity,
            si.total,
            s.sale_date
        FROM sale_items si
        JOIN products p ON si.product_id = p.id
        JOIN sales s ON si.sale_id = s.id
        ORDER BY s.sale_date DESC;
    """)
    sales = cur.fetchall()

    return render_template("report.html", purchases=purchases, sales=sales)

@main.route("/report/export")
@login_required
def export_report():
    cur = mysql.connection.cursor()

    # Pembelian
    cur.execute("""
        SELECT pr.name, p.quantity, p.purchase_price, p.purchase_date
        FROM purchases p
        JOIN products pr ON p.product_id = pr.id
        ORDER BY p.purchase_date DESC
    """)
    purchases = cur.fetchall()
    df_purchases = pd.DataFrame(purchases, columns=["Produk", "Jumlah", "Total", "Tanggal"])

    # Penjualan
    cur.execute("""
        SELECT
            p.name,
            si.quantity,
            s.grand_total,
            s.sale_date
        FROM sale_items si
        JOIN products p ON si.product_id = p.id
        JOIN sales s ON si.sale_id = s.id
        ORDER BY s.sale_date DESC;
    """)
    sales = cur.fetchall()
    df_sales = pd.DataFrame(sales, columns=["Produk", "Jumlah", "Total", "Tanggal"])

    # Buat Excel dengan dua sheet
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_purchases.to_excel(writer, sheet_name="Pembelian", index=False)
        df_sales.to_excel(writer, sheet_name="Penjualan", index=False)

    output.seek(0)
    return send_file(output, download_name="laporan_transaksi.xlsx", as_attachment=True)



@main.route("/report/pdf")
@login_required
def export_pdf():
    cur = mysql.connection.cursor()

    # Ambil data pembelian
    cur.execute("""
        SELECT pr.name AS Produk, p.quantity AS Jumlah, p.purchase_price AS Total, p.purchase_date AS Tanggal
        FROM purchases p
        JOIN products pr ON p.product_id = pr.id
        ORDER BY p.purchase_date DESC
    """)
    purchases = cur.fetchall()

    # Ambil data penjualan
    cur.execute("""
        SELECT p.name AS Produk, si.quantity AS Jumlah, s.grand_total AS Total, s.sale_date AS Tanggal
        FROM sale_items si
        JOIN products p ON si.product_id = p.id
        JOIN sales s ON si.sale_id = s.id
        ORDER BY s.sale_date DESC
    """)
    sales = cur.fetchall()

    # Render ke HTML
    html = render_template("report_pdf.html", purchases=purchases, sales=sales, now=datetime.now())

    # Konversi ke PDF
    result = io.BytesIO()
    pisa.CreatePDF(io.StringIO(html), dest=result)
    result.seek(0)

    response = make_response(result.read())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f"inline; filename=Laporan Transaksi.pdf"
    return response


# ------------------------
# SUMMARY
# ------------------------

@main.route("/summary", methods=["GET", "POST"])
@login_required
def summary():
    if current_user.role != 'admin':
        flash("Hanya admin yang bisa mengakses halaman ini.", "danger")
        return redirect(url_for("main.dashboard"))

    cur = mysql.connection.cursor()

    # Tambah modal
    if request.method == "POST":
        modal_awal = float(request.form["modal_awal"])
        cur.execute("INSERT INTO summary (modal_awal) VALUES (%s)", (modal_awal,))
        mysql.connection.commit()
        flash("Data summary berhasil disimpan", "success")
        return redirect(url_for("main.summary"))

    # Ambil semua summary
    cur.execute("SELECT id, modal_awal, created_at FROM summary ORDER BY created_at DESC LIMIT 1")
    summaries = cur.fetchall()
    result = []

    for s in summaries:
        summary_id = s[0]
        modal_awal = s[1]
        tanggal = s[2].date()

        # Total pembelian dari tanggal summary ini
        cur.execute("""
            SELECT SUM(total) FROM purchases
            WHERE DATE(created_at) >= %s
        """, (tanggal,))
        total_pembelian = cur.fetchone()[0] or 0

        # Total penjualan dari tanggal summary ini
        cur.execute("""
            SELECT SUM(total) FROM sale_items
            WHERE DATE(created_at) >= %s
        """, (tanggal,))
        total_penjualan = cur.fetchone()[0] or 0

        # Profit
        total_profit = total_penjualan - total_pembelian - modal_awal

        result.append((summary_id, modal_awal, total_pembelian, total_penjualan, total_profit, tanggal))

    return render_template("summary/summary.html", all_summaries=result)




# Route Edit Summary
@main.route("/summary/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_summary(id):
    if current_user.role != "admin":
        flash("Akses ditolak", "danger")
        return redirect(url_for("dashboard"))

    cur = mysql.connection.cursor()
    if request.method == "POST":
        modal_awal = request.form["modal_awal"]
        cur.execute("UPDATE summary SET modal_awal = %s WHERE id = %s", (modal_awal, id))
        mysql.connection.commit()
        flash("Data summary berhasil diperbarui", "success")
        return redirect(url_for("main.summary"))

    cur.execute("SELECT * FROM summary WHERE id = %s", (id,))
    summary = cur.fetchone()
    return render_template("summary/edit_summary.html", summary=summary)


#add_modal
@main.route("/summary/add", methods=["GET", "POST"])
@login_required
def add_modal():
    if current_user.role != 'admin':
        flash("Hanya admin yang bisa mengakses halaman ini.", "danger")
        return redirect(url_for("main.dashboard"))

    cur = mysql.connection.cursor()

    if request.method == "POST":
        modal_baru = float(request.form["modal_awal"])

        cursor = mysql.connection.cursor()

        # Ambil total modal_awal terakhir (baris paling akhir berdasarkan tanggal)
        cursor.execute("SELECT modal_awal FROM summary ORDER BY created_at DESC LIMIT 1")
        last_modal = cursor.fetchone()
        total_modal_sebelumnya = last_modal[0] if last_modal else 0

        # Jumlahkan modal baru
        modal_awal = float(total_modal_sebelumnya) + modal_baru

        # Hitung pembelian & penjualan dinamis
        cur.execute("SELECT SUM(total) FROM purchases")
        total_pembelian = cur.fetchone()[0] or 0

        cur.execute("SELECT SUM(total) FROM sale_items")
        total_penjualan = cur.fetchone()[0] or 0

        # Hitung profit = penjualan - pembelian
        total_profit = total_penjualan - total_pembelian

        cur.execute("""
            INSERT INTO summary (modal_awal)
            VALUES (%s)
        """, (modal_awal,))
        mysql.connection.commit()

        flash("Data summary berhasil ditambahkan.", "success")
        return redirect(url_for("main.summary"))

    return render_template("summary/add_modal.html")



# Route Hapus Summary
@main.route("/summary/delete/<int:id>", methods=["GET"])
@login_required
def delete_summary(id):
    if current_user.role != "admin":
        flash("Akses ditolak", "danger")
        return redirect(url_for("dashboard"))

    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM summary")
    mysql.connection.commit()
    flash("Data summary berhasil dihapus", "success")
    return redirect(url_for("main.summary"))


@main.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("main.login"))
