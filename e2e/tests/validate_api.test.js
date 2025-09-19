import { test, expect } from '@playwright/test';
import { readFileSync } from 'fs';
import { basename } from 'path';
import { statSync } from 'fs';
import { createAuthHeader, createFormData } from './utils.js';

const BASE_URL = 'http://localhost:8000';
const TEST_CREDENTIALS = 'root:root';

function findAndReadFileSync(filepath) {
    
    if (statSync(filepath, { throwIfNoEntry: false })?.isFile()) {
        return readFileSync(filepath);        
    } else if (statSync('e2e/' + filepath, { throwIfNoEntry: false })?.isFile()) {
        return readFileSync('e2e/' + filepath);
    }
    throw new Error(`File does not exist: ${filepath}`);
}

function createFormDataForTwoFiles(filePath1, filePath2) {

    const name1 = basename(filePath1);
    const file1 = new File([findAndReadFileSync(filePath1)], name1);
    const name2 = basename(filePath2);
    const file2 = new File([findAndReadFileSync(filePath2)], name2);

    const form = new FormData();
    form.append('file', file1);
    form.append('file_name', name1);
    form.append('file', file2);
    form.append('file_name', name2);
    return form;
}

function createDummyFormData(fileName, fileSize) {

    // create a buffer with zeros of specified size
    const largeBuffer = Buffer.alloc(fileSize, 0); 
    const file = new File([largeBuffer], fileName);
    const form = new FormData();
    form.append('file', file);
    form.append('file_name', fileName);
    return form;
}

test.describe('API - ValidationRequest', () => {

    test('POST accepts valid file', async ({ request }) => {

        // try to post a valid file
        const response = await request.post(`${BASE_URL}/api/validationrequest/`, {
            headers: createAuthHeader(TEST_CREDENTIALS),
            multipart: createFormData('fixtures/valid_file.ifc')
        });

        // check if the response is correct - 201 Created
        expect(response.statusText()).toBe('Created');
        expect(response.status()).toBe(201);
    });

    test('POST without trailing slash accepts valid file', async ({ request }) => {

        // try to post a valid file
        const response = await request.post(`${BASE_URL}/api/validationrequest`, {
            headers: createAuthHeader(TEST_CREDENTIALS),
            multipart: createFormData('fixtures/valid_file.ifc')
        });

        // check if the response is correct - 201 Created
        expect(response.statusText()).toBe('Created');
        expect(response.status()).toBe(201);
    });

    test('POST implements file size limit', async ({ request }) => {

        // try to post a large file
        const response = await request.post(`${BASE_URL}/api/validationrequest/`, {
            headers: createAuthHeader(TEST_CREDENTIALS),
            multipart: createDummyFormData('very_large_file.ifc', 300 * 1024 * 1024) // 300 MB (> 256 MB limit)
        });

        // check if the response is correct - 413 Payload Too Large
        expect(response.statusText()).toBe('Request Entity Too Large');
        expect(response.status()).toBe(413); 

        // check if the error details are correct
        expect(await response.json()).toEqual({ message: 'File size exceeds allowed file size limit (256 MB).' });
    });

    test('POST rejects empty file', async ({ request }) => {

        // try to post an empty file
        const response = await request.post(`${BASE_URL}/api/validationrequest/`, {
            headers: createAuthHeader(TEST_CREDENTIALS),
            multipart: createFormData('fixtures/empty_file.ifc')
        });

        // check if the response is correct - 400 Bad Request
        expect(response.statusText()).toBe('Bad Request');
        expect(response.status()).toBe(400); 
        expect(await response.json()).toEqual({ file: [ 'The submitted file is empty.' ] });
    });

    test('POST rejects empty file name', async ({ request }) => {

        // try to post a file with empty filename
        const response = await request.post(`${BASE_URL}/api/validationrequest/`, {
            headers: createAuthHeader(TEST_CREDENTIALS),
            multipart: createFormData('fixtures/valid_file.ifc', '')
        });

        // check if the response is correct - 400 Bad Request
        expect(response.statusText()).toBe('Bad Request');
        expect(response.status()).toBe(400); 
        expect(await response.json()).toStrictEqual({
            "file": [ "The submitted data was not a file. Check the encoding type on the form." ], 
            "file_name": [ "This field is required." ]
        });
    });

    test('POST only accepts *.ifc files', async ({ request }) => {

        // try to post a file with invalid file extension
        const response = await request.post(`${BASE_URL}/api/validationrequest/`, {
            headers: createAuthHeader(TEST_CREDENTIALS),
            multipart: createFormData('fixtures/invalid_file_extension')
        });

        // check if the response is correct - 400 Bad Request
        expect(response.statusText()).toBe('Bad Request');
        expect(response.status()).toBe(400); 
        expect(await response.json()).toEqual({ file_name: "File name must end with '.ifc'." });
    });

    test('POST only accepts a single file (for now)', async ({ request }) => {

        // try to post two valid files
        const response = await request.post(`${BASE_URL}/api/validationrequest/`, {
            headers: createAuthHeader(TEST_CREDENTIALS),
            multipart: createFormDataForTwoFiles(
                'fixtures/valid_file.ifc', 
                'fixtures/valid_file2.ifc'
            )
        });

        // check if the response is correct - 400 Bad Request
        expect(response.statusText()).toBe('Bad Request');
        expect(response.status()).toBe(400); 
        expect(await response.json()).toEqual({ message: 'Only one file can be uploaded at a time.' });
    });

    test('POST without authorization header returns 401', async ({ request }) => {

        // try to post a valid file but without authorization header
        const response = await request.post(`${BASE_URL}/api/validationrequest/`, {
            multipart: createFormData('fixtures/valid_file.ifc')
        });

        // check if the response is correct - 401 Unauthorized
        expect(response.statusText()).toBe('Unauthorized');
        expect(response.status()).toBe(401);
    });

    test('GET returns a single instance', async ({ request }) => {

        // post a valid file
        let response = await request.post(`${BASE_URL}/api/validationrequest/`, {
            headers: createAuthHeader(TEST_CREDENTIALS),
            multipart: createFormData('fixtures/valid_file.ifc')
        });
        const json_body = await response.json();
        const public_id = json_body['public_id'];

        // retrieve a single instance
        response = await request.get(`${BASE_URL}/api/validationrequest/${public_id}`, {
            headers: createAuthHeader(TEST_CREDENTIALS)
        });

        // check if the response is correct - 200 OK
        expect(response.statusText()).toBe('OK');
        expect(response.status()).toBe(200);

        // check if the json body is correct
        const data = await response.json();
        expect(data).toBeInstanceOf(Object);
        expect(data).toHaveProperty('public_id');
        expect(data['public_id']).toBe(public_id);
    });

    test('GET with trailing slash returns a single instance', async ({ request }) => {

        // post a valid file
        let response = await request.post(`${BASE_URL}/api/validationrequest/`, {
            headers: createAuthHeader(TEST_CREDENTIALS),
            multipart: createFormData('fixtures/valid_file.ifc')
        });
        const json_body = await response.json();
        const public_id = json_body['public_id'];

        // retrieve a single instance
        response = await request.get(`${BASE_URL}/api/validationrequest/${public_id}/`, {
            headers: createAuthHeader(TEST_CREDENTIALS)
        });

        // check if the response is correct - 200 OK
        expect(response.statusText()).toBe('OK');
        expect(response.status()).toBe(200);

        // check if the json body is correct
        const data = await response.json();
        expect(data).toBeInstanceOf(Object);
        expect(data).toHaveProperty('public_id');
        expect(data['public_id']).toBe(public_id);
    });

    test('GET with "public_id" query param returns a list with one object', async ({ request }) => {

        // post a valid file
        let response = await request.post(`${BASE_URL}/api/validationrequest/`, {
            headers: createAuthHeader(TEST_CREDENTIALS),
            multipart: createFormData('fixtures/valid_file.ifc')
        });
        const json_body = await response.json();
        const public_id = json_body['public_id'];
        const file_name = json_body['file_name']

        // retrieve a single instance
        response = await request.get(`${BASE_URL}/api/validationrequest/?public_id=${public_id}`, {
            headers: createAuthHeader(TEST_CREDENTIALS)
        });

        // check if the response is correct - 200 OK
        expect(response.statusText()).toBe('OK');
        expect(response.status()).toBe(200);

        // check if the json body is correct
        const data = await response.json();
        expect(data).toBeInstanceOf(Object);
        expect(Array.isArray(data.results)).toBe(true);
        expect(data.results.length).toBe(1);
        expect(data.results[0]).toHaveProperty('public_id');
        expect(data.results[0]['public_id']).toBe(public_id);
        expect(data.results[0]['file_name']).toBe(file_name);
        expect(data).toHaveProperty('metadata.result_set.total');
        expect(data).toHaveProperty('metadata.result_set.limit');
    });

    test('GET returns a list', async ({ request }) => {

        // post a valid file
        let response = await request.post(`${BASE_URL}/api/validationrequest/`, {
            headers: createAuthHeader(TEST_CREDENTIALS),
            multipart: createFormData('fixtures/valid_file.ifc')
        });

        // retrieve list of ValidationRequests
        response = await request.get(`${BASE_URL}/api/validationrequest/`, {
            headers: createAuthHeader(TEST_CREDENTIALS)
        });

        // check if the response is correct - 200 OK
        expect(response.statusText()).toBe('OK');
        expect(response.status()).toBe(200);

        // check if the json body is correct
        const data = await response.json();
        expect(data).toBeInstanceOf(Object);
        expect(Array.isArray(data.results)).toBe(true);
        expect(data.results.length).toBeGreaterThan(0);
        expect(data.results[0]).toHaveProperty('public_id');
        expect(data.results[0]).toHaveProperty('file_name');
        expect(data).toHaveProperty('metadata.result_set.total');
    });

    test('GET without trailing slash returns a list', async ({ request }) => {

        // post a valid file
        let response = await request.post(`${BASE_URL}/api/validationrequest/`, {
            headers: createAuthHeader(TEST_CREDENTIALS),
            multipart: createFormData('fixtures/valid_file.ifc')
        });

        // retrieve list of ValidationRequests
        response = await request.get(`${BASE_URL}/api/validationrequest`, {
            headers: createAuthHeader(TEST_CREDENTIALS)
        });

        // check if the response is correct - 200 OK
        expect(response.statusText()).toBe('OK');
        expect(response.status()).toBe(200);

        // check if the json body is correct
        const data = await response.json();
        expect(data).toBeInstanceOf(Object);
        expect(Array.isArray(data.results)).toBe(true);
        expect(data.results.length).toBe(25);
        expect(data.results[0]).toHaveProperty('public_id');
        expect(data).toHaveProperty('metadata.result_set.total');
        expect(data).toHaveProperty('metadata.result_set.limit');
    });

    test('GET without authorization header returns 401', async ({ request }) => {

        // retrieve list of ValidationRequests
        const response = await request.get(`${BASE_URL}/api/validationrequest/`);

        // check if the response is correct - 401 Unauthorized
        expect(response.statusText()).toBe('Unauthorized');
        expect(response.status()).toBe(401);
    });

    test('pagination: offset window has no overlap with first page', async ({ request }) => {
        const first = await request.get(`${BASE_URL}/api/validationrequest/`, {
          headers: createAuthHeader(TEST_CREDENTIALS)
        });
        const page1 = await first.json();
        const total = page1.metadata.result_set.total;
      
        test.skip(total < 50, 'not enough data to test two full pages');
      
        const second = await request.get(`${BASE_URL}/api/validationrequest/?offset=25&limit=25`, {
          headers: createAuthHeader(TEST_CREDENTIALS)
        });
        const page2 = await second.json();
      
        const page1Ids = new Set(page1.results.map(r => r.public_id));
        const overlap = page2.results.filter(r => page1Ids.has(r.public_id));
        expect(overlap.length).toBe(0);
      
        expect(page1.results.length).toBeLessThanOrEqual(25);
        expect(page2.results.length).toBeLessThanOrEqual(25);
      });

      test('pagination: limit works', async ({ request }) => {
        const res = await request.get(`${BASE_URL}/api/validationrequest/?limit=5`, {
          headers: createAuthHeader(TEST_CREDENTIALS)
        });
        const data = await res.json();
        expect(Array.isArray(data.results)).toBe(true);
        expect(data.results.length).toBeLessThanOrEqual(5);
        expect(data.metadata.result_set.limit).toBe(5);
      });

      test('pagination: correct ordering', async ({ request }) => {
        const res = await request.get(`${BASE_URL}/api/validationrequest/`, {
          headers: createAuthHeader(TEST_CREDENTIALS)
        });
        const data = await res.json();
      
        // ordering: newest first
        if (data.results.length >= 2) {
          const t0 = new Date(data.results[0].created).getTime();
          const t1 = new Date(data.results[1].created).getTime();
          expect(t0).toBeGreaterThanOrEqual(t1);
        }
      });
});

test.describe('API - Browsers vs Clients', () => {

    test('Browsers will be redirected to /api/swagger-ui', async ({ request }) => {

        // root of /api
        const response = await request.get(`${BASE_URL}/api/`, {
            headers: {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8'
            },
            maxRedirects: 0
        });

        // check if the response is correct - 302 Found
        expect(response.statusText()).toBe('Found');
        expect(response.status()).toBe(302);
        expect(response.headers()['location']).toBe('/api/swagger-ui/');
    });

    test('Browsers are redirected to /api/swagger-ui', async ({ request }) => {

        // root of /api
        const response = await request.get(`${BASE_URL}/api/`, {
            headers: {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8'
            },
            maxRedirects: 5
        });

        // check if the response is correct - 200 OK
        expect(response.statusText()).toBe('OK');
        expect(response.status()).toBe(200);
        expect(response.url()).toBe(`${BASE_URL}/api/swagger-ui/`);
    });

    test('API clients will be redirected to /api/schema', async ({ request }) => {

        // root of /api
        const response = await request.get(`${BASE_URL}/api/`, {
            maxRedirects: 0
        });

        // check if the response is correct - 302 Found
        expect(response.statusText()).toBe('Found');
        expect(response.status()).toBe(302);
        expect(response.headers()['location']).toBe('/api/schema/');
    });

    test('API clients are redirected to /api/schema', async ({ request }) => {

        // root of /api
        const response = await request.get(`${BASE_URL}/api/`, {
            maxRedirects: 5
        });

        // check if the response is correct - 200 OK
        expect(response.statusText()).toBe('OK');
        expect(response.status()).toBe(200);
        expect(response.url()).toBe(`${BASE_URL}/api/schema/`);
    });  

});