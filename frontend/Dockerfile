# syntax=docker/dockerfile:1
FROM node:22-alpine

WORKDIR /app

# -- 国内 npm 源 --
RUN npm config set registry https://registry.npmmirror.com

# -- 依赖层（先 COPY package.json，利用缓存）--
COPY package.json package-lock.json* ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci 2>/dev/null || npm install

# -- 源码层 --
COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
