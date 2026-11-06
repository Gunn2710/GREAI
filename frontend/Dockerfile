# syntax=docker/dockerfile:1
# Frontend: build the React app, serve it with nginx (which also proxies /api
# to the backend container). Build context is frontend/.

# --- Build stage -----------------------------------------------------------------
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# Vite bakes VITE_* variables into the JavaScript at build time. Only the Clerk
# publishable key goes here; it is public by design. Empty = dev-auth mode.
ARG VITE_CLERK_PUBLISHABLE_KEY=""
RUN VITE_CLERK_PUBLISHABLE_KEY="$VITE_CLERK_PUBLISHABLE_KEY" npm run build

# --- Runtime stage: unprivileged nginx on port 8080 --------------------------------
FROM nginxinc/nginx-unprivileged:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
