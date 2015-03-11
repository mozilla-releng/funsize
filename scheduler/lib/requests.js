import request from 'superagent-promise';
import config from '../config/rail.js';
import fs from 'fs';

var r = request.get('https://aus4-admin.mozilla.org/api/releases').
  ca(fs.readFileSync(config.balrog.ca)).
  auth(config.balrog.credentials.username, config.balrog.credentials.password).
  query({product: 'Firefox', version: '36.0'}).
  accept('application/json').
  end();

r.then((res) => {
  if (res.ok) {
    console.log('sweet', res.body);
  } else {
    console.log("err", res);
  }
}).catch((err) => {
  if (err){
    console.log("error", err);
    return;
  }
});
