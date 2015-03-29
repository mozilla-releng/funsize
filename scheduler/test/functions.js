import {suite, test} from 'mocha';
import assert from 'assert';
import {interestingBuilderName} from '../lib/functions.js';

suite('interestingBuilderName', () => {

  test('should match Firefox nightly build', () => {
    assert(interestingBuilderName('Linux mozilla-central nightly'));
  });
  test('should match Firefox Win nightly build', () => {
    assert(interestingBuilderName('WINNT 5.2 mozilla-aurora nightly'));
  });
  test('should match Thunderbird nightly build', () => {
    assert(interestingBuilderName('TB WINNT 5.2 comm-aurora nightly'));
  });
  test('should match Firefox win64 nightly build', () => {
    assert(interestingBuilderName('WINNT 6.1 x86-64 mozilla-aurora nightly'));
  });
  test('should match Firefox mac nightly build', () => {
    assert(interestingBuilderName('OS X 10.7 mozilla-central nightly'));
  });

  test('should not match Firefox mac xulrunner nightly build', () => {
    assert(!interestingBuilderName('OS X 10.7 mozilla-central xulrunner nightly'));
  });
  test('should not match Firefox asan nightly build', () => {
    assert(!interestingBuilderName('Linux x86-64 mozilla-central asan nightly'));
  });
  test('should not match B2g nightly build', () => {
    assert(!interestingBuilderName('b2g_mozilla-central_nexus-5-l_nightly'));
  });

});
