# multi-stage dockerfile for coding-agent frontend
# builds react app with vite and serves with nginx

# stage 1: builder - install deps and build
FROM node:20-alpine AS builder

WORKDIR /app

# copy package files first for better layer caching
COPY package.json package-lock.json* ./

# install dependencies
RUN npm ci

# copy source files
COPY . .

# build the production bundle
RUN npm run build

# stage 2: runtime - nginx serving static files
FROM nginx:alpine

# copy built assets from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# copy custom nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# expose port 80
EXPOSE 80

# nginx runs in foreground by default in official image
CMD ["nginx", "-g", "daemon off;"]
