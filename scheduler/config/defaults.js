module.exports = {
  balrog: {
    api_root: process.env.BALROG_API_ROOT,
    credentials: {
      username: process.env.BALROG_PASSWORD,
      password: process.env.BALROG_PASSWORD
    }
  },
  pulse: {
    credentials: {
      username: process.env.PULSE_USERNAME,
      password: process.env.PULSE_PASSWORD
    },
    queueName: process.env.FUNSIZE_QUEUE_NAME
  },
  taskcluster: {
    credentials: {
      clientId: process.env.TASKCLUSTER_CLIENT_ID,
      accessToken: process.env.TASKCLUSTER_ACCESS_TOKEN
    }
  },
  funsize: {
    logDir: '/home/worker/funsize-logs'
  }
};
