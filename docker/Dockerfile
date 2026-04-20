# Example Dockerfile for OpenMailBot backend
FROM node:20
WORKDIR /app
COPY ../backend ./backend
RUN cd backend && npm install
CMD ["npm", "start", "--prefix", "backend"]
