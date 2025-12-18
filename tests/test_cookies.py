import streamlit as st
import extra_streamlit_components as arg

cookie_manager = arg.CookieManager()

st.title("Cookie Test")

if st.button("Set Cookie"):
    cookie_manager.set("test_cookie", "hello_world")
    st.success("Cookie set!")

if st.button("Get Cookie"):
    val = cookie_manager.get("test_cookie")
    st.write(f"Cookie val from manager: {val}")

st.write("Current Cookies from context:", st.context.cookies)
