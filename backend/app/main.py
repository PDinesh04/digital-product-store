import os, math, hashlib, hmac, secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, ForeignKey, DateTime, func
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship
from jose import jwt, JWTError
import stripe

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./store.db")
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()
security = HTTPBearer()

app = FastAPI(title="Digital Product Store", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    role = Column(String(20), default="USER")
    created_at = Column(DateTime, default=datetime.utcnow)
    cart = relationship("Cart", back_populates="user", uselist=False)
    orders = relationship("Order", back_populates="user")

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(String(1000), default="")
    price = Column(Float, nullable=False)
    image_url = Column(String(500), default="")
    is_active = Column(Boolean, default=True)

class Cart(Base):
    __tablename__ = "carts"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    user = relationship("User", back_populates="cart")
    items = relationship("CartItem", back_populates="cart", cascade="all, delete-orphan")

class CartItem(Base):
    __tablename__ = "cart_items"
    id = Column(Integer, primary_key=True)
    cart_id = Column(Integer, ForeignKey("carts.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Integer, default=1)
    cart = relationship("Cart", back_populates="items")
    product = relationship("Product")

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    total = Column(Float, default=0)
    status = Column(String(20), default="PENDING")
    stripe_session_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    payment = relationship("Payment", back_populates="order", uselist=False, cascade="all, delete-orphan")

class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    product_name = Column(String(200))
    price = Column(Float)
    quantity = Column(Integer)
    order = relationship("Order", back_populates="items")

class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), unique=True)
    amount = Column(Float)
    status = Column(String(20), default="PENDING")
    stripe_payment_intent = Column(String(255), nullable=True)
    order = relationship("Order", back_populates="payment")

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120000).hex()
    return f"{salt}${digest}"

def verify_password(password, stored):
    try:
        salt, digest = stored.split("$", 1)
        check = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120000).hex()
        return hmac.compare_digest(check, digest)
    except Exception:
        return False

def token_for(user):
    return jwt.encode({"sub": str(user.id), "role": user.role,
                       "exp": datetime.utcnow()+timedelta(hours=12)}, SECRET_KEY, algorithm="HS256")

def current_user(creds: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(creds.credentials, SECRET_KEY, algorithms=["HS256"])
        uid = int(payload["sub"])
        user = db.get(User, uid)
        if not user: raise HTTPException(401, "Invalid token")
        return user
    except (JWTError, ValueError):
        raise HTTPException(401, "Invalid token")

def admin_user(user=Depends(current_user)):
    if user.role != "ADMIN": raise HTTPException(403, "Admin only")
    return user

class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=4)

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class ProductIn(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""
    price: float = Field(gt=0)
    image_url: str = ""

class CartIn(BaseModel):
    product_id: int
    quantity: int = Field(default=1, ge=1)

class QtyIn(BaseModel):
    quantity: int = Field(ge=1)

@app.get("/")
def root(): return {"message": "Digital Product Store API is running"}

@app.get("/health")
def health(): return {"status": "ok"}

@app.post("/auth/register", status_code=201)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    if db.query(User).filter_by(email=data.email).first():
        raise HTTPException(400, "Email already registered")
    role = "ADMIN" if db.query(User).count() == 0 else "USER"
    user = User(email=data.email, password=hash_password(data.password), role=role)
    db.add(user); db.commit(); db.refresh(user)
    return {"id": user.id, "email": user.email, "role": user.role, "access_token": token_for(user)}

@app.post("/auth/login")
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=data.email).first()
    if not user or not verify_password(data.password, user.password):
        raise HTTPException(401, "Invalid credentials")
    return {"access_token": token_for(user), "user": {"id": user.id, "email": user.email, "role": user.role}}

@app.get("/auth/profile")
def profile(user=Depends(current_user)):
    return {"id": user.id, "email": user.email, "role": user.role}

def product_dict(p):
    return {"id": p.id, "name": p.name, "description": p.description, "price": p.price,
            "image_url": p.image_url, "is_active": p.is_active}

@app.post("/products", status_code=201)
def create_product(data: ProductIn, db: Session = Depends(get_db), user=Depends(admin_user)):
    p = Product(**data.model_dump())
    db.add(p); db.commit(); db.refresh(p)
    return product_dict(p)

@app.get("/products")
def products(page: int = Query(1, ge=1), limit: int = Query(10, ge=1, le=100),
             search: str = "", db: Session = Depends(get_db)):
    q = db.query(Product).filter(Product.is_active == True)
    if search: q = q.filter(Product.name.ilike(f"%{search}%"))
    total = q.count()
    items = q.offset((page-1)*limit).limit(limit).all()
    return {"items": [product_dict(x) for x in items], "page": page, "limit": limit,
            "total": total, "total_pages": math.ceil(total/limit) if total else 0}

@app.get("/products/{product_id}")
def get_product(product_id: int, db: Session = Depends(get_db)):
    p = db.get(Product, product_id)
    if not p or not p.is_active: raise HTTPException(404, "Product not found")
    return product_dict(p)

@app.put("/products/{product_id}")
def update_product(product_id: int, data: ProductIn, db: Session = Depends(get_db), user=Depends(admin_user)):
    p = db.get(Product, product_id)
    if not p: raise HTTPException(404, "Product not found")
    for k,v in data.model_dump().items(): setattr(p,k,v)
    db.commit(); db.refresh(p)
    return product_dict(p)

@app.delete("/products/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db), user=Depends(admin_user)):
    p = db.get(Product, product_id)
    if not p: raise HTTPException(404, "Product not found")
    p.is_active = False; db.commit()
    return {"message": "Product deleted"}

def get_cart(db, user):
    cart = db.query(Cart).filter_by(user_id=user.id).first()
    if not cart:
        cart = Cart(user_id=user.id); db.add(cart); db.commit(); db.refresh(cart)
    return cart

@app.get("/cart")
def view_cart(db: Session = Depends(get_db), user=Depends(current_user)):
    cart = get_cart(db,user)
    items=[]; total=0
    for i in cart.items:
        if i.product and i.product.is_active:
            line=i.product.price*i.quantity; total+=line
            items.append({"id":i.id,"product_id":i.product_id,"name":i.product.name,
                          "price":i.product.price,"quantity":i.quantity,"subtotal":line})
    return {"items":items,"total":round(total,2)}

@app.post("/cart/items")
def add_cart(data: CartIn, db: Session = Depends(get_db), user=Depends(current_user)):
    p=db.get(Product,data.product_id)
    if not p or not p.is_active: raise HTTPException(404,"Product not found")
    cart=get_cart(db,user)
    item=db.query(CartItem).filter_by(cart_id=cart.id,product_id=p.id).first()
    if item: item.quantity += data.quantity
    else: db.add(CartItem(cart_id=cart.id,product_id=p.id,quantity=data.quantity))
    db.commit()
    return {"message":"Product added to cart"}

@app.put("/cart/items/{item_id}")
def update_cart(item_id:int,data:QtyIn,db:Session=Depends(get_db),user=Depends(current_user)):
    item=db.get(CartItem,item_id); cart=get_cart(db,user)
    if not item or item.cart_id != cart.id: raise HTTPException(404,"Cart item not found")
    item.quantity=data.quantity; db.commit(); return {"message":"Quantity updated"}

@app.delete("/cart/items/{item_id}")
def remove_cart(item_id:int,db:Session=Depends(get_db),user=Depends(current_user)):
    item=db.get(CartItem,item_id); cart=get_cart(db,user)
    if not item or item.cart_id != cart.id: raise HTTPException(404,"Cart item not found")
    db.delete(item); db.commit(); return {"message":"Product removed"}

@app.delete("/cart")
def clear_cart(db:Session=Depends(get_db),user=Depends(current_user)):
    cart=get_cart(db,user)
    for i in list(cart.items): db.delete(i)
    db.commit(); return {"message":"Cart cleared"}

@app.post("/payments/create-checkout-session")
def checkout(db:Session=Depends(get_db),user=Depends(current_user)):
    cart=get_cart(db,user)
    valid=[i for i in cart.items if i.product and i.product.is_active]
    if not valid: raise HTTPException(400,"Cart is empty")
    order=Order(user_id=user.id,total=sum(i.product.price*i.quantity for i in valid),status="PENDING")
    db.add(order); db.flush()
    for i in valid:
        db.add(OrderItem(order_id=order.id,product_id=i.product_id,product_name=i.product.name,
                         price=i.product.price,quantity=i.quantity))
    db.add(Payment(order_id=order.id,amount=order.total,status="PENDING"))
    db.commit(); db.refresh(order)
    if not STRIPE_SECRET_KEY:
        return {"order_id":order.id,"checkout_url":f"{FRONTEND_URL}/orders","demo":True}
    try:
        stripe.api_key=STRIPE_SECRET_KEY
        session=stripe.checkout.Session.create(
            mode="payment", line_items=[{"price_data":{"currency":"usd","product_data":{"name":i.product.name},
            "unit_amount":int(i.product.price*100)},"quantity":i.quantity} for i in valid],
            success_url=f"{FRONTEND_URL}/orders?success=1", cancel_url=f"{FRONTEND_URL}/cart",
            metadata={"order_id":str(order.id)})
        order.stripe_session_id=session.id; db.commit()
        return {"order_id":order.id,"checkout_url":session.url}
    except Exception as e:
        order.status="FAILED"; order.payment.status="FAILED"; db.commit()
        raise HTTPException(400,f"Stripe error: {e}")

@app.post("/payments/webhook")
async def stripe_webhook(request: Request, db:Session=Depends(get_db)):
    payload=await request.body()
    sig=request.headers.get("stripe-signature")
    if STRIPE_WEBHOOK_SECRET:
        try: event=stripe.Webhook.construct_event(payload,sig,STRIPE_WEBHOOK_SECRET)
        except Exception: raise HTTPException(400,"Invalid webhook")
    else:
        try: event=await request.json()
        except Exception: raise HTTPException(400,"Invalid webhook")
    if event.get("type") in ("checkout.session.completed","checkout.session.async_payment_succeeded"):
        obj=event["data"]["object"]; oid=(obj.get("metadata") or {}).get("order_id")
        if oid:
            order=db.get(Order,int(oid))
            if order:
                order.status="PAID"; order.payment.status="PAID"
                db.commit()
    elif event.get("type") == "checkout.session.expired":
        obj=event["data"]["object"]; oid=(obj.get("metadata") or {}).get("order_id")
        if oid:
            order=db.get(Order,int(oid))
            if order: order.status="CANCELLED"; order.payment.status="CANCELLED"; db.commit()
    return {"received":True}

@app.get("/orders")
def orders(page:int=Query(1,ge=1),limit:int=Query(5,ge=1,le=100),db:Session=Depends(get_db),user=Depends(current_user)):
    q=db.query(Order).filter_by(user_id=user.id); total=q.count()
    rows=q.order_by(Order.created_at.desc()).offset((page-1)*limit).limit(limit).all()
    return {"items":[{"id":o.id,"total":o.total,"status":o.status,"created_at":o.created_at,"payment_status":o.payment.status if o.payment else None} for o in rows],
            "page":page,"limit":limit,"total":total,"total_pages":math.ceil(total/limit) if total else 0}

@app.get("/orders/{order_id}")
def order_detail(order_id:int,db:Session=Depends(get_db),user=Depends(current_user)):
    o=db.get(Order,order_id)
    if not o or (o.user_id!=user.id and user.role!="ADMIN"): raise HTTPException(404,"Order not found")
    return {"id":o.id,"total":o.total,"status":o.status,"payment_status":o.payment.status if o.payment else None,
            "items":[{"product_id":i.product_id,"name":i.product_name,"price":i.price,"quantity":i.quantity} for i in o.items]}

@app.get("/admin/stats")
def admin_stats(db:Session=Depends(get_db),user=Depends(admin_user)):
    return {"total_products":db.query(Product).filter_by(is_active=True).count(),
            "total_orders":db.query(Order).count(),
            "paid_orders":db.query(Order).filter_by(status="PAID").count(),
            "total_revenue":db.query(func.coalesce(func.sum(Order.total),0)).filter_by(status="PAID").scalar()}

@app.get("/admin/orders")
def admin_orders(db:Session=Depends(get_db),user=Depends(admin_user)):
    return [{"id":o.id,"user_id":o.user_id,"total":o.total,"status":o.status} for o in db.query(Order).order_by(Order.id.desc()).all()]

@app.get("/admin/reports")
def reports(db:Session=Depends(get_db),user=Depends(admin_user)):
    revenue=db.query(func.coalesce(func.sum(Order.total),0)).filter_by(status="PAID").scalar()
    popular=db.query(OrderItem.product_name,func.sum(OrderItem.quantity).label("qty")).join(Order).filter(Order.status=="PAID").group_by(OrderItem.product_name).order_by(func.sum(OrderItem.quantity).desc()).all()
    never=db.query(Product).filter(~Product.id.in_(db.query(OrderItem.product_id))).all()
    return {"total_revenue":revenue,"most_purchased":[{"product":x[0],"quantity":x[1]} for x in popular],
            "never_purchased":[p.name for p in never]}
