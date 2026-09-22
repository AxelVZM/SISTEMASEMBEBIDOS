module.exports = {
  apps: [{
    name: 'andes-maqanakuy',
    script: './server.js',
    cwd: __dirname,
    instances: 1,
    exec_mode: 'fork',
    autorestart: true,
    watch: false,
    max_memory_restart: '350M',
    env: {
      NODE_ENV: 'production',
      HOST: '0.0.0.0',
      PORT: 3000,
      AUTO_PORT_FALLBACK: 'false'
    }
  }]
};
