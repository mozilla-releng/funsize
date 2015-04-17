module.exports = {
  balrog: {
    api_root: process.env.BALROG_API_ROOT,
    // cert: 'file name in data dir',
    credentials: {
      username: process.env.BALROG_USERNAME,
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
    //logDir: process.env.FUNSIZE_LOGDIR
  }
};
