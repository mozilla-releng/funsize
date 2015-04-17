'use strict';
import request from 'superagent-promise';
import fs from 'fs';
import _ from 'lodash';
import path from 'path';
import {log} from './logging';

var platform_map = JSON.parse(fs.readFileSync(path.join(__dirname, '../data/platforms.js')));

export class BalrogClient {
  constructor(api_root, credentials, cert) {
    this.api_root = api_root;
    this.credentials = credentials;
    if (cert) {
      this.cert = fs.readFileSync(path.join(__dirname, '../data', cert));
    } else {
      this.cert = null;
    }
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
      // add nightly-2 to filter out not dated blobs
      name_prefix: `${product}-${branch}-nightly-2`
    };
    log.debug("Fetching %s with params", url, params);
    let r = await request.get(url).
      ca(this.cert).
      auth(this.credentials.username, this.credentials.password).
      query(params).
      accept('application/json').
      end();
    let releases = r.body.releases;
    log.debug("got releases:", releases);
    if (!options.includeLatest) {
      releases = _.filter(releases, (release) => ! _.endsWith(release.name, '-latest'));
    }
    releases = _.sortByOrder(releases, 'name', ! options.reverse);
    releases = _.take(releases, options.limit);
    log.debug("filtered:", releases);
    return releases;
  }

  async getBuild(release, platform, locale) {
    let balrog_platform = platform_map[platform][0];
    let url = `${this.api_root}/releases/${release}/builds/${balrog_platform}/${locale}`;
    log.debug("Fetching %s", url);
    let r = await request.get(url).
      ca(this.cert).
      auth(this.credentials.username, this.credentials.password).
      accept('application/json').
      end();
    log.debug("Got build:", r.body);
    return r.body;
  }
}
