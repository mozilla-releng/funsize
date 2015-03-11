'use strict';
import request from 'superagent-promise';
import config from '../config/rail.js';
import fs from 'fs';
import _ from 'lodash';
import path from 'path';

var platform_map = JSON.parse(fs.readFileSync(path.join(__dirname, 'platforms.js')));
var cert = fs.readFileSync(config.balrog.ca);

export class BalrogClient {
  constructor(api_root, credentials) {
    this.api_root = api_root;
    this.credentials = credentials;
  }

  async getReleases(product, branch, options={}) {
    options = _.defaults(options, {
      limit: 2,
      includeLatest: false,
      reverse: true
    });

    let url = `${this.api_root}/releases`;
    let params = {
      product: product,
      name_prefix: `${product}-${branch}`
    };
    let r = await request.get(url).
      ca(cert).
      auth(this.credentials.username, this.credentials.password).
      query(params).
      accept('application/json').end();
    let releases = r.body.releases;
    if (!options.includeLatest) {
      releases = _.filter(releases, (release) => ! _.endsWith(release.name, '-latest'));
    }
    releases = _.sortByOrder(releases, 'name', ! options.reverse);
    //releases = releases.slice(0, options.limit-1);
    releases = _.take(releases, options.limit);
    return releases;
  }

  async getBuild(release, platform, locale) {
    let balrog_platform = platform_map[platform][0];
    let url = `${this.api_root}/releases/${release}/builds/${balrog_platform}/${locale}`;
    let r = await request.get(url).
      ca(cert).
      auth(this.credentials.username, this.credentials.password).
      accept('application/json').end();
    return r.body;
  }
}


async function getReleases(product) {
  let c = new BalrogClient('https://aus4-admin.mozilla.org/api', config.balrog.credentials);
  let releases = await c.getReleases('Firefox', 'mozilla-central', {limit: 3});
  let minus2 = _.last(releases);
  let platform= platform_map['win32'][0];
  let build = await c.getBuild(minus2.name, platform, 'en-US');
}
