import os
import smtplib
import secrets

from email.message import EmailMessage
from datetime import date, datetime, timedelta
from itertools import combinations
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel, EmailStr, Field

from sqlalchemy import (
    create_engine,
    Column,
    BigInteger,
    Integer,
    String,
    Boolean,
    Text,
    DateTime,
    ForeignKey,
    select,
)

from sqlalchemy.orm import (
    declarative_base,
    sessionmaker,
    Session,
)


# =========================================================
# CONFIGURATION
# =========================================================

load_dotenv(
    os.path.join(
        os.path.dirname(__file__),
        ".env"
    )
)


DATABASE_URL = os.getenv("DATABASE_URL")

SMTP_HOST = os.getenv(
    "SMTP_HOST",
    "smtp.gmail.com"
)

SMTP_PORT = int(
    os.getenv(
        "SMTP_PORT",
        "587"
    )
)

SMTP_USERNAME = os.getenv(
    "SMTP_USERNAME"
)

SMTP_PASSWORD = os.getenv(
    "SMTP_PASSWORD"
)

RESTAURANT_EMAIL = os.getenv(
    "RESTAURANT_EMAIL",
    "filipatanasovski87@gmail.com"
)

RESTAURANT_ID = 1

RESTAURANT_NAME = "District 11"

RESTAURANT_TIMEZONE = "Europe/Belgrade"


# =========================================================
# VALIDATE CONFIGURATION
# =========================================================

if not DATABASE_URL:

    raise RuntimeError(
        "DATABASE_URL is not configured."
    )


if not SMTP_USERNAME:

    raise RuntimeError(
        "SMTP_USERNAME is not configured."
    )


if not SMTP_PASSWORD:

    raise RuntimeError(
        "SMTP_PASSWORD is not configured."
    )


# =========================================================
# DATABASE
# =========================================================

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)


SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


Base = declarative_base()


# =========================================================
# DATABASE MODELS
# =========================================================


class Restaurant(Base):

    __tablename__ = "restaurants"

    id = Column(
        BigInteger,
        primary_key=True,
    )

    name = Column(
        String,
        nullable=False,
    )

    address = Column(
        Text
    )

    timezone = Column(
        String,
        nullable=False,
    )


class RestaurantTable(Base):

    __tablename__ = "restaurant_tables"

    id = Column(
        BigInteger,
        primary_key=True,
    )

    restaurant_id = Column(
        BigInteger,
        ForeignKey(
            "restaurants.id"
        ),
        nullable=False,
    )

    table_number = Column(
        Integer,
        nullable=False,
    )

    capacity = Column(
        Integer,
        nullable=False,
    )

    active = Column(
        Boolean,
        nullable=False,
    )


class Customer(Base):

    __tablename__ = "customers"

    id = Column(
        BigInteger,
        primary_key=True,
    )

    name = Column(
        String,
        nullable=False,
    )

    email = Column(
        String
    )

    phone = Column(
        String
    )

    created_at = Column(
        DateTime(
            timezone=True
        ),
        nullable=False,
    )


class Reservation(Base):

    __tablename__ = "reservations"

    id = Column(
        BigInteger,
        primary_key=True,
    )

    restaurant_id = Column(
        BigInteger,
        ForeignKey(
            "restaurants.id"
        ),
        nullable=False,
    )

    customer_id = Column(
        BigInteger,
        ForeignKey(
            "customers.id"
        ),
        nullable=False,
    )

    start_at = Column(
        DateTime(
            timezone=True
        ),
        nullable=False,
    )

    end_at = Column(
        DateTime(
            timezone=True
        ),
        nullable=False,
    )

    party_size = Column(
        Integer,
        nullable=False,
    )

    status = Column(
        String,
        nullable=False,
    )

    confirmation_code = Column(
        String,
        unique=True,
    )

    notes = Column(
        Text
    )

    created_at = Column(
        DateTime(
            timezone=True
        ),
        nullable=False,
    )

    updated_at = Column(
        DateTime(
            timezone=True
        ),
        nullable=False,
    )


class ReservationTable(Base):

    __tablename__ = "reservation_tables"

    reservation_id = Column(
        BigInteger,
        ForeignKey(
            "reservations.id"
        ),
        primary_key=True,
    )

    table_id = Column(
        BigInteger,
        ForeignKey(
            "restaurant_tables.id"
        ),
        primary_key=True,
    )


# =========================================================
# FASTAPI
# =========================================================

app = FastAPI(
    title="District 11 Restaurant API",
    version="2.0.0"
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,

    allow_origins=[
        "*"
    ],

    allow_credentials=False,

    allow_methods=[
        "*"
    ],

    allow_headers=[
        "*"
    ],
)


# =========================================================
# DATABASE DEPENDENCY
# =========================================================

def get_db():

    db = SessionLocal()

    try:

        yield db

    finally:

        db.close()


# =========================================================
# RESERVATION REQUEST MODEL
# =========================================================

class ReservationRequest(BaseModel):

    name: str = Field(
        ...,
        min_length=2,
        max_length=100
    )

    email: EmailStr

    date: date

    time: str = Field(
        ...,
        min_length=5,
        max_length=5
    )

    party_size: int = Field(
        ...,
        ge=1,
        le=50
    )

    phone: str = Field(
        ...,
        min_length=3,
        max_length=30
    )

    message: str = Field(
        default="",
        max_length=2000
    )

    duration_minutes: int = Field(
        default=120,
        ge=1,
        le=1440
    )


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/")
def root():

    return {
        "status": "online",
        "service": "District 11 Restaurant API"
    }


@app.get("/api/health")
def health():

    return {
        "status": "ok",
        "restaurant": RESTAURANT_NAME,
        "restaurant_id": RESTAURANT_ID
    }


# =========================================================
# GET RESTAURANT
# =========================================================

def get_restaurant(
    db: Session
):

    restaurant = db.get(
        Restaurant,
        RESTAURANT_ID
    )

    if restaurant is None:

        raise HTTPException(
            status_code=500,
            detail=(
                "District 11 restaurant "
                "with ID 1 was not found "
                "in the database."
            )
        )

    return restaurant


# =========================================================
# PARSE RESERVATION DATETIME
# =========================================================

def parse_reservation_datetime(
    reservation_date: date,
    reservation_time: str
):

    try:

        parsed_time = datetime.strptime(
            reservation_time,
            "%H:%M"
        ).time()

    except ValueError:

        raise HTTPException(
            status_code=400,
            detail=(
                "Neispravno vreme. "
                "Koristite format HH:MM."
            )
        )

    restaurant_timezone = ZoneInfo(
        RESTAURANT_TIMEZONE
    )

    start_at = datetime.combine(
        reservation_date,
        parsed_time
    ).replace(
        tzinfo=restaurant_timezone
    )

    return start_at


# =========================================================
# FIND AVAILABLE TABLES
# =========================================================

def find_best_tables(
    db: Session,
    restaurant_id: int,
    start_at: datetime,
    end_at: datetime,
    party_size: int
):

    # -----------------------------------------------------
    # GET ACTIVE TABLES
    # -----------------------------------------------------

    tables = db.execute(

        select(RestaurantTable)

        .where(

            RestaurantTable.restaurant_id
            == restaurant_id,

            RestaurantTable.active.is_(True)

        )

        .order_by(
            RestaurantTable.capacity.asc(),
            RestaurantTable.table_number.asc()
        )

    ).scalars().all()


    if not tables:

        return None


    # -----------------------------------------------------
    # FIND TABLES USED BY OVERLAPPING RESERVATIONS
    # -----------------------------------------------------

    reserved_table_ids = db.execute(

        select(
            ReservationTable.table_id
        )

        .join(
            Reservation,
            Reservation.id
            == ReservationTable.reservation_id
        )

        .where(

            Reservation.restaurant_id
            == restaurant_id,

            Reservation.status.in_(
                [
                    "pending",
                    "confirmed"
                ]
            ),

            Reservation.start_at < end_at,

            Reservation.end_at > start_at

        )

    ).scalars().all()


    reserved_table_ids = set(
        reserved_table_ids
    )


    # -----------------------------------------------------
    # REMOVE OCCUPIED TABLES
    # -----------------------------------------------------

    available_tables = [

        table

        for table in tables

        if table.id not in reserved_table_ids

    ]


    if not available_tables:

        return None


    # -----------------------------------------------------
    # FIND SMALLEST TABLE COMBINATION
    # -----------------------------------------------------

    best_combination = None

    best_capacity = None


    for number_of_tables in range(
        1,
        len(available_tables) + 1
    ):

        for combination in combinations(
            available_tables,
            number_of_tables
        ):

            capacity = sum(
                table.capacity
                for table in combination
            )


            if capacity < party_size:

                continue


            # Prefer:
            #
            # 1. Fewest tables
            # 2. Smallest excess capacity
            #

            if best_combination is None:

                best_combination = combination

                best_capacity = capacity

                continue


            if len(combination) < len(
                best_combination
            ):

                best_combination = combination

                best_capacity = capacity

                continue


            if (
                len(combination)
                == len(best_combination)
                and capacity
                < best_capacity
            ):

                best_combination = combination

                best_capacity = capacity


    return best_combination


# =========================================================
# CHECK AVAILABILITY
# =========================================================

@app.get(
    "/api/reservations/availability"
)
def check_availability(

    date_value: str,

    time: str,

    party_size: int,

    duration_minutes: int = 120,

    db: Session = Depends(get_db)

):

    if party_size <= 0:

        raise HTTPException(
            status_code=400,
            detail="Broj osoba mora biti veći od 0."
        )


    if duration_minutes <= 0:

        raise HTTPException(
            status_code=400,
            detail="Trajanje mora biti veće od 0."
        )


    # -----------------------------------------------------
    # PARSE DATE
    # -----------------------------------------------------

    try:

        reservation_date = date.fromisoformat(
            date_value
        )

    except ValueError:

        raise HTTPException(
            status_code=400,
            detail=(
                "Neispravan datum. "
                "Koristite YYYY-MM-DD."
            )
        )


    # -----------------------------------------------------
    # CHECK PAST
    # -----------------------------------------------------

    if reservation_date < date.today():

        raise HTTPException(
            status_code=400,
            detail=(
                "Datum rezervacije "
                "ne može biti u prošlosti."
            )
        )


    # -----------------------------------------------------
    # PARSE TIME
    # -----------------------------------------------------

    start_at = parse_reservation_datetime(
        reservation_date,
        time
    )


    end_at = (
        start_at
        + timedelta(
            minutes=duration_minutes
        )
    )


    # -----------------------------------------------------
    # FIND TABLES
    # -----------------------------------------------------

    tables = find_best_tables(
        db=db,
        restaurant_id=RESTAURANT_ID,
        start_at=start_at,
        end_at=end_at,
        party_size=party_size
    )


    if tables is None:

        return {

            "available": False,

            "restaurant": RESTAURANT_NAME,

            "date": date_value,

            "time": time,

            "party_size": party_size,

            "message": (
                "Nema slobodnih stolova "
                "za izabrani termin."
            )

        }


    return {

        "available": True,

        "restaurant": RESTAURANT_NAME,

        "date": date_value,

        "time": time,

        "party_size": party_size,

        "tables": [

            {
                "id": table.id,
                "table_number": table.table_number,
                "capacity": table.capacity
            }

            for table in tables

        ]

    }


# =========================================================
# SMTP EMAIL
# =========================================================

def send_email(
    recipient: str,
    subject: str,
    body: str,
    reply_to: str | None = None
):

    if not SMTP_HOST:

        raise RuntimeError(
            "SMTP_HOST is not configured."
        )


    if not SMTP_USERNAME:

        raise RuntimeError(
            "SMTP_USERNAME is not configured."
        )


    if not SMTP_PASSWORD:

        raise RuntimeError(
            "SMTP_PASSWORD is not configured."
        )


    message = EmailMessage()

    message["Subject"] = subject

    message["From"] = SMTP_USERNAME

    message["To"] = recipient


    if reply_to:

        message["Reply-To"] = reply_to


    message.set_content(
        body
    )


    with smtplib.SMTP(
        SMTP_HOST,
        SMTP_PORT,
        timeout=20
    ) as server:

        server.ehlo()

        server.starttls()

        server.ehlo()

        server.login(
            SMTP_USERNAME,
            SMTP_PASSWORD
        )

        server.send_message(
            message
        )


# =========================================================
# EMAIL RESTAURANT
# =========================================================

def send_restaurant_email(
    reservation,
    customer,
    restaurant,
    tables
):

    table_numbers = ", ".join(

        f"Sto {table.table_number}"

        for table in tables

    )


    subject = (
        f"Nova rezervacija - "
        f"{customer.name} - "
        f"{reservation.start_at.strftime('%d.%m.%Y')} "
        f"{reservation.start_at.strftime('%H:%M')}"
    )


    body = f"""
NOVA REZERVACIJA
================

Restoran:
{restaurant.name}

Ime i prezime:
{customer.name}

Imejl:
{customer.email or "Nije naveden"}

Telefon:
{customer.phone or "Nije naveden"}

Datum:
{reservation.start_at.strftime('%d.%m.%Y')}

Vreme:
{reservation.start_at.strftime('%H:%M')}

Broj osoba:
{reservation.party_size}

Sto:
{table_numbers}

Potvrdni kod:
{reservation.confirmation_code}

Napomena:
{reservation.notes or "Nema dodatne poruke."}


STATUS:
Rezervacija je automatski potvrđena i upisana u bazu.


Ova rezervacija je poslata preko
District 11 internet stranice.
"""


    send_email(

        recipient=RESTAURANT_EMAIL,

        subject=subject,

        body=body,

        reply_to=(
            customer.email
            if customer.email
            else None
        )

    )


# =========================================================
# EMAIL CUSTOMER
# =========================================================

def send_customer_confirmation(
    reservation,
    customer,
    restaurant,
    tables
):

    table_numbers = ", ".join(

        f"Sto {table.table_number}"

        for table in tables

    )


    subject = (
        f"Potvrda rezervacije - "
        f"{restaurant.name}"
    )


    body = f"""
Poštovani/a {customer.name},

Vaša rezervacija u restoranu
{restaurant.name}
je uspešno potvrđena.


DETALJI REZERVACIJE
===================

Restoran:
{restaurant.name}

Datum:
{reservation.start_at.strftime('%d.%m.%Y')}

Vreme:
{reservation.start_at.strftime('%H:%M')}

Broj osoba:
{reservation.party_size}

Sto:
{table_numbers}

Potvrdni kod:
{reservation.confirmation_code}

Telefon:
{customer.phone or "Nije naveden"}

Napomena:
{reservation.notes or "Nema dodatne poruke."}


Hvala vam na poverenju i
radujemo se vašoj poseti!


District 11 Brunch Bar & Restaurant

Pasterova 14b
Beograd, Srbija



---------------------------------------------------------
ENGLISH
---------------------------------------------------------

Dear {customer.name},

Your reservation at
{restaurant.name}
has been successfully confirmed.


RESERVATION DETAILS
===================

Restaurant:
{restaurant.name}

Date:
{reservation.start_at.strftime('%d.%m.%Y')}

Time:
{reservation.start_at.strftime('%H:%M')}

Number of guests:
{reservation.party_size}

Table:
{table_numbers}

Confirmation code:
{reservation.confirmation_code}

Phone:
{customer.phone or "Not provided"}

Message:
{reservation.notes or "No additional message."}


Thank you for choosing us.

We look forward to welcoming you!


District 11 Brunch Bar & Restaurant

Pasterova 14b
Belgrade, Serbia
"""


    send_email(

        recipient=str(
            customer.email
        ),

        subject=subject,

        body=body

    )


# =========================================================
# CREATE RESERVATION
# =========================================================

@app.post(
    "/api/reservations"
)
def create_reservation(

    reservation_request: ReservationRequest,

    db: Session = Depends(get_db)

):

    # =====================================================
    # RESTAURANT
    # =====================================================

    restaurant = get_restaurant(
        db
    )


    # =====================================================
    # DATE CHECK
    # =====================================================

    if (
        reservation_request.date
        < date.today()
    ):

        raise HTTPException(

            status_code=400,

            detail=(
                "Datum rezervacije "
                "ne može biti u prošlosti."
            )

        )


    # =====================================================
    # DATETIME
    # =====================================================

    start_at = parse_reservation_datetime(

        reservation_request.date,

        reservation_request.time

    )


    end_at = (

        start_at

        + timedelta(
            minutes=
            reservation_request.duration_minutes
        )

    )


    # =====================================================
    # CHECK IF REQUESTED TIME IS IN THE PAST
    # =====================================================

    now = datetime.now(
        ZoneInfo(
            RESTAURANT_TIMEZONE
        )
    )


    if start_at < now:

        raise HTTPException(

            status_code=400,

            detail=(
                "Vreme rezervacije "
                "ne može biti u prošlosti."
            )

        )


    # =====================================================
    # FIND AVAILABLE TABLES
    # =====================================================

    tables = find_best_tables(

        db=db,

        restaurant_id=restaurant.id,

        start_at=start_at,

        end_at=end_at,

        party_size=
            reservation_request.party_size

    )


    if tables is None:

        raise HTTPException(

            status_code=409,

            detail=(
                "Nažalost, nema slobodnih "
                "stolova za izabrani termin."
            )

        )


    # =====================================================
    # FIND EXISTING CUSTOMER
    # =====================================================

    customer = db.execute(

        select(Customer)

        .where(
            Customer.email
            == str(
                reservation_request.email
            )
        )

    ).scalar_one_or_none()


    # =====================================================
    # CREATE CUSTOMER
    # =====================================================

    if customer is None:

        customer = Customer(

            name=
                reservation_request.name,

            email=
                str(
                    reservation_request.email
                ),

            phone=
                reservation_request.phone,

            created_at=
                datetime.utcnow()

        )

        db.add(
            customer
        )

        db.flush()


    else:

        customer.name = (
            reservation_request.name
        )

        customer.phone = (
            reservation_request.phone
        )


    # =====================================================
    # GENERATE CONFIRMATION CODE
    # =====================================================

    confirmation_code = None


    for _ in range(10):

        candidate = (
            secrets.token_hex(4)
            .upper()
        )


        existing_code = db.execute(

            select(Reservation)

            .where(
                Reservation.confirmation_code
                == candidate
            )

        ).scalar_one_or_none()


        if existing_code is None:

            confirmation_code = candidate

            break


    if confirmation_code is None:

        raise HTTPException(

            status_code=500,

            detail=(
                "Could not generate "
                "a reservation confirmation code."
            )

        )


    # =====================================================
    # CREATE RESERVATION
    # =====================================================

    current_time = datetime.utcnow()


    reservation = Reservation(

        restaurant_id=
            restaurant.id,

        customer_id=
            customer.id,

        start_at=
            start_at,

        end_at=
            end_at,

        party_size=
            reservation_request.party_size,

        status=
            "confirmed",

        confirmation_code=
            confirmation_code,

        notes=
            reservation_request.message,

        created_at=
            current_time,

        updated_at=
            current_time

    )


    db.add(
        reservation
    )

    db.flush()


    # =====================================================
    # ASSIGN TABLES
    # =====================================================

    for table in tables:

        reservation_table = ReservationTable(

            reservation_id=
                reservation.id,

            table_id=
                table.id

        )

        db.add(
            reservation_table
        )


    # =====================================================
    # COMMIT DATABASE
    # =====================================================

    try:

        db.commit()

        db.refresh(
            reservation
        )

    except Exception:

        db.rollback()

        raise HTTPException(

            status_code=500,

            detail=(
                "Greška prilikom "
                "čuvanja rezervacije."
            )

        )


    # =====================================================
    # SEND EMAILS
    # =====================================================

    restaurant_email_error = None

    customer_email_error = None


    # -----------------------------------------------------
    # RESTAURANT EMAIL
    # -----------------------------------------------------

    try:

        send_restaurant_email(

            reservation=
                reservation,

            customer=
                customer,

            restaurant=
                restaurant,

            tables=
                tables

        )

    except Exception as error:

        restaurant_email_error = str(
            error
        )

        print(
            "Restaurant email failed:",
            error
        )


    # -----------------------------------------------------
    # CUSTOMER EMAIL
    # -----------------------------------------------------

    try:

        send_customer_confirmation(

            reservation=
                reservation,

            customer=
                customer,

            restaurant=
                restaurant,

            tables=
                tables

        )

    except Exception as error:

        customer_email_error = str(
            error
        )

        print(
            "Customer email failed:",
            error
        )


    # =====================================================
    # RESPONSE
    # =====================================================

    return {

        "success": True,

        "message": (
            "Rezervacija je uspešno "
            "kreirana."
        ),

        "reservation": {

            "id":
                reservation.id,

            "restaurant":
                restaurant.name,

            "name":
                customer.name,

            "email":
                customer.email,

            "phone":
                customer.phone,

            "date":
                reservation.start_at.strftime(
                    "%Y-%m-%d"
                ),

            "time":
                reservation.start_at.strftime(
                    "%H:%M"
                ),

            "party_size":
                reservation.party_size,

            "status":
                reservation.status,

            "confirmation_code":
                reservation.confirmation_code,

            "tables": [

                {

                    "id":
                        table.id,

                    "table_number":
                        table.table_number,

                    "capacity":
                        table.capacity

                }

                for table in tables

            ]

        },

        "emails": {

            "restaurant_sent":
                restaurant_email_error
                is None,

            "customer_sent":
                customer_email_error
                is None

        }

    }