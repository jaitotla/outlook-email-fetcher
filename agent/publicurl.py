from pyngrok import ngrok

# Open a tunnel to localhost:5051
public_url = ngrok.connect(5051)

print("Public URL:", public_url)