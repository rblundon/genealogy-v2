FROM node:20-slim

WORKDIR /app

# Copy package files first for caching
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy application source
COPY . .

# Expose Vite dev server port
EXPOSE 5173

# Run Vite dev server with host binding for external access
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
