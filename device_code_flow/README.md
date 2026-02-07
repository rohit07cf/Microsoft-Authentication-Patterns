# Device Code Flow

> **Status:** Not yet implemented.

The Device Code flow is designed for input-constrained devices (smart TVs, IoT devices, CLI tools) that cannot display a browser. The app shows a code and a URL; the user navigates to that URL on a separate device, enters the code, and signs in.

## When to use

- CLI tools where opening a browser is impractical or not possible.
- IoT or embedded devices with no keyboard/browser.
- SSH sessions or remote terminals.

## Key MSAL API

```python
app = msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY)
flow = app.initiate_device_flow(scopes=["User.Read"])
print(flow["message"])  # "To sign in, use a web browser to open https://microsoft.com/devicelogin and enter the code XXXXXXX"
result = app.acquire_token_by_device_flow(flow)
```
