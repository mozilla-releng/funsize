'use strict';
import request from 'superagent-promise';
import config from '../config/rail.js';
import fs from 'fs';
import _ from 'lodash';
import path from 'path';
import {log} from './logging';

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
    log.debug("Fetching %s with params %j", url, params);
    let r = await request.get(url).
      ca(cert).
      auth(this.credentials.username, this.credentials.password).
      query(params).
      accept('application/json').end();
    let releases = r.body.releases;
    log.debug("got releases: %j", releases);
    if (!options.includeLatest) {
      releases = _.filter(releases, (release) => ! _.endsWith(release.name, '-latest'));
    }
    releases = _.sortByOrder(releases, 'name', ! options.reverse);
    releases = _.take(releases, options.limit);
    log.debug("filtered: %j", releases);
    return releases;
  }

  async getBuild(release, platform, locale) {
    let balrog_platform = platform_map[platform][0];
    let url = `${this.api_root}/releases/${release}/builds/${balrog_platform}/${locale}`;
    log.debug("Fetching %s", url);
    let r = await request.get(url).
      ca(cert).
      auth(this.credentials.username, this.credentials.password).
      accept('application/json').end();
    log.debug("Got build: %j", r.body);
    return r.body;
  }
}
