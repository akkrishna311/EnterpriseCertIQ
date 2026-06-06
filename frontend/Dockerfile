# EnterpriseCertIQ frontend — Vite build served by nginx, proxying /api + /health
# to the backend container. Build:
#   docker build -t enterprisecertiq-frontend ./frontend
# Run (point at backend):
#   docker run -p 5173:80 -e BACKEND_URL=https://<backend-app>.azurecontainerapps.io frontend
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
# nginx.conf is a template; BACKEND_URL is substituted at container start.
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
ENV BACKEND_URL=http://backend:8000
EXPOSE 80
# nginx:alpine auto-runs envsubst on /etc/nginx/templates/*.template → /etc/nginx/conf.d/
