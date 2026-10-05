import React,{useState,useEffect} from "react";
import {createRoot} from "react-dom/client";
import {BrowserRouter,useNavigate,Routes,Route,Link,useParams} from "react-router-dom";
import axios from "axios";
import {ToastContainer,toast} from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import "./style.css";

const API=import.meta.env.VITE_API_URL||"http://127.0.0.1:8000";
const api=axios.create({baseURL:API});
api.interceptors.request.use(c=>{const t=localStorage.getItem("token");if(t)c.headers.Authorization=`Bearer ${t}`;return c});

function Nav(){return <nav className="p-4 bg-slate-900 text-white flex gap-5"><Link to="/products">Products</Link><Link to="/cart">Cart</Link><Link to="/orders">Orders</Link><Link to="/login">Login</Link><Link to="/register">Register</Link><Link to="/admin/products">Admin</Link></nav>}
function Login(){
  const [f,setF]=useState({email:"",password:""});
  const n=useNavigate();

  const go=async()=>{
    try{
      let r=await api.post("/auth/login",f);
      localStorage.setItem("token",r.data.access_token);
      toast.success("Login successful");
      n("/products");
    }catch(e){
      toast.error(e.response?.data?.detail||"Invalid credentials");
    }
  };

  return (
    <Box title="Login">
      <Input p="email" f={f} s={setF}/>
      <Input p="password" f={f} s={setF}/>
      <button onClick={go} className="btn">Login</button>
    </Box>
  );
}
function Register(){const [f,setF]=useState({email:"",password:""});const n=useNavigate();const go=async()=>{try{let r=await api.post("/auth/register",f);localStorage.setItem("token",r.data.access_token);toast.success("Registration successful");n("/products")}catch(e){toast.error(e.response?.data?.detail||"Registration failed")}};return <Box title="Register"><Input p="email" f={f} s={setF}/><Input p="password" f={f} s={setF}/><button onClick={go} className="btn">Register</button></Box>}
function Input({p,f,s}){return <input className="border p-2 w-full mb-3" type={p==="password"?"password":"text"} placeholder={p} value={f[p]} onChange={e=>s({...f,[p]:e.target.value})}/>}

function Products(){const [d,setD]=useState({items:[],total_pages:0,page:1});const [q,setQ]=useState("");const load=p=>api.get(`/products?page=${p}&limit=6&search=${q}`).then(r=>setD(r.data));useEffect(()=>{load(1)},[q]);return <div><h1 className="title">Digital Products</h1><input className="border p-2 mb-4" placeholder="Search..." value={q} onChange={e=>setQ(e.target.value)}/><div className="grid md:grid-cols-3 gap-4">{d.items.map(p=><div className="card" key={p.id}><h2 className="font-bold">{p.name}</h2><p>{p.description}</p><p className="font-bold">${p.price}</p><button className="btn" onClick={async()=>{try{await api.post("/cart/items",{product_id:p.id,quantity:1});toast.success("Product added to cart")}catch(e){toast.error("Please login")}}}>Add to cart</button></div>)}</div><div className="flex gap-2 mt-5"><button className="btn" disabled={d.page<=1} onClick={()=>load(d.page-1)}>Previous</button>{Array.from({length:d.total_pages},(_,i)=><button className="border px-3" onClick={()=>load(i+1)}>{i+1}</button>)}<button className="btn" disabled={d.page>=d.total_pages} onClick={()=>load(d.page+1)}>Next</button></div></div>}

function Cart(){const [d,setD]=useState({items:[],total:0});const load=()=>api.get("/cart").then(r=>setD(r.data)).catch(()=>toast.error("Login required"));useEffect(load,[]);const pay=async()=>{try{let r=await api.post("/payments/create-checkout-session");window.location.href=r.data.checkout_url}catch(e){toast.error(e.response?.data?.detail||"Payment failed")}};return <div><h1 className="title">Cart</h1>{d.items.map(i=><div className="card mb-2">{i.name} × {i.quantity} = ${i.subtotal}<button className="ml-5 text-red-600" onClick={async()=>{await api.delete(`/cart/items/${i.id}`);toast.success("Product removed");load()}}>Remove</button></div>)}<h2 className="text-xl font-bold">Total: ${d.total}</h2><button className="btn mt-3" onClick={pay}>Checkout</button></div>}

function Orders(){const [d,setD]=useState({items:[]});useEffect(()=>{api.get("/orders").then(r=>setD(r.data)).catch(()=>toast.error("Login required"))},[]);return <div><h1 className="title">My Orders</h1>{d.items.map(o=><div className="card mb-2">Order #{o.id} — ${o.total} — <b>{o.status}</b> / {o.payment_status}</div>)}</div>}
function Admin(){const [s,setS]=useState({});const [p,setP]=useState({name:"",description:"",price:10});const load=()=>api.get("/admin/stats").then(r=>setS(r.data)).catch(()=>toast.error("Admin login required"));useEffect(load,[]);const add=async()=>{try{await api.post("/products",p);toast.success("Product created");load()}catch(e){toast.error(e.response?.data?.detail||"Admin only")}};return <div><h1 className="title">Admin Dashboard</h1><div className="grid grid-cols-4 gap-3">{Object.entries(s).map(([k,v])=><div className="card"><b>{k}</b><div>{v}</div></div>)}</div><div className="card mt-5"><h2 className="font-bold">Create Product</h2><input className="border p-2 block mb-2" placeholder="name" onChange={e=>setP({...p,name:e.target.value})}/><input className="border p-2 block mb-2" placeholder="description" onChange={e=>setP({...p,description:e.target.value})}/><input className="border p-2 block mb-2" type="number" placeholder="price" onChange={e=>setP({...p,price:Number(e.target.value)})}/><button className="btn" onClick={add}>Create</button></div></div>}

function Detail(){const {id}=useParams();const [p,setP]=useState(null);useEffect(()=>{api.get(`/products/${id}`).then(r=>setP(r.data))},[id]);return p?<div className="card"><h1 className="title">{p.name}</h1><p>{p.description}</p><p>${p.price}</p></div>:null}
function Box({title,children}){return <div className="max-w-md mx-auto"><h1 className="title">{title}</h1><div className="card">{children}</div></div>}
function App(){return <><Nav/><main className="p-6 max-w-6xl mx-auto"><Routes><Route path="/" element={<Products/>}/><Route path="/products" element={<Products/>}/><Route path="/products/:id" element={<Detail/>}/><Route path="/cart" element={<Cart/>}/><Route path="/orders" element={<Orders/>}/><Route path="/login" element={<Login/>}/><Route path="/register" element={<Register/>}/><Route path="/admin/products" element={<Admin/>}/><Route path="/admin/orders" element={<Admin/>}/></Routes></main><ToastContainer/></>}
createRoot(document.getElementById("root")).render(<BrowserRouter><App/></BrowserRouter>);
