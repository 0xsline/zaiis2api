#!/usr/bin/env python3
from playwright.sync_api import sync_playwright
import json
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    
    print("[*] 打开 zai.is...")
    page.goto("https://zai.is/auth")
    
    print("[*] 请登录，登录后会自动保存...")
    
    # 等待跳转到 chat
    page.wait_for_url("**/chat**", timeout=300000)
    print("[+] 登录成功!")
    time.sleep(5)
    
    # 保存 cookies
    cookies = context.cookies()
    with open("cookies.json", "w") as f:
        json.dump(cookies, f, indent=2)
    print(f"[+] 保存了 {len(cookies)} 个 cookies")
    
    # 获取 localStorage
    storage = page.evaluate("""() => {
        let data = {};
        for(let i=0; i<localStorage.length; i++) {
            let k = localStorage.key(i);
            data[k] = localStorage.getItem(k);
        }
        return data;
    }""")
    with open("storage.json", "w") as f:
        json.dump(storage, f, indent=2)
    print(f"[+] 保存了 localStorage")
    print(storage)
    
    browser.close()
    print("[+] 完成!")
