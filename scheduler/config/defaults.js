module.exports = {
  pulse: {
    credentials: {
      username: '',
      password: ''
    },
    // Giving a name makes the queue durable
    // queueName: 'test-q', maxLength: 50
  },
  taskcluster: {
    credentials: {
      clientId: '',
      accessToken: ''
    }
  },
  worker: {
    workerType: 'b2gtest',
    image: 'rail/funsize-update-generator'
  }
};
