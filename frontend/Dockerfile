FROM node:22-slim AS build
WORKDIR /app
COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile
COPY . .
RUN yarn build

FROM nginx:stable
COPY --from=build /app/dist/frontend/browser /usr/share/nginx/html
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# nginx's docker-entrypoint.sh runs envsubst on templates/*.template using
# env vars into /etc/nginx/conf.d/ automatically. Render injects $PORT at
# runtime and requires the service to bind to it on 0.0.0.0 - do not hardcode.
ENV PORT=10000
EXPOSE 10000
