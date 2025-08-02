import { test, expect } from '@playwright/test';
import { readFileSync } from 'fs';
import { basename } from 'path';

const BASE_URL = 'http://localhost:8000';
const TEST_CREDENTIALS = 'root:root';

test.describe('API - ValidationRequest', () => {

    test('POST accepts valid file', async ({ request }) => {

        // try to post a valid file
        const file_path = 'e2e/fixtures/valid_file.ifc';
        const file_name = basename(file_path);
        const file = new File([readFileSync(file_path)], file_name);
        const form = new FormData();
        form.append('file', file);
        form.append('file_name', file_name);

        let hash = btoa(TEST_CREDENTIALS);
        const response = await request.post(`${BASE_URL}/api/validationrequest/`, {
            headers: {
                'Authorization': `Basic ${hash}`,
            },
            multipart: form
        });

        // check if the response is correct - 201 Created
        expect(response.statusText()).toBe('Created');
        expect(response.status()).toBe(201);
    });

    test('POST without trailing slash accepts valid file', async ({ request }) => {

        // try to post a valid file
        const file_path = 'e2e/fixtures/valid_file.ifc';
        const file_name = basename(file_path);
        const file = new File([readFileSync(file_path)], file_name);
        const form = new FormData();
        form.append('file', file);
        form.append('file_name', file_name);

        let hash = btoa(TEST_CREDENTIALS);
        const response = await request.post(`${BASE_URL}/api/validationrequest`, {
            headers: {
                'Authorization': `Basic ${hash}`,
            },
            multipart: form
        });

        // check if the response is correct - 201 Created
        expect(response.statusText()).toBe('Created');
        expect(response.status()).toBe(201);
    });

    test('POST implements file size limit', async ({ request }) => {

        // try to post a large file
        const file_name = 'very_large_file.ifc';
        const largeBuffer = Buffer.alloc(300 * 1024 * 1024, 0); // 300 MB of dummy data (> 256 MB limit)
        const file = new File([largeBuffer], file_name);
        const form = new FormData();
        form.append('file', file);
        form.append('file_name', file_name);

        let hash = btoa(TEST_CREDENTIALS);
        const response = await request.post(`${BASE_URL}/api/validationrequest/`, {
            headers: {
                'Authorization': `Basic ${hash}`,
            },
            multipart: form
        });

        // check if the response is correct - 413 Payload Too Large
        expect(response.statusText()).toBe('Request Entity Too Large');
        expect(response.status()).toBe(413); 
        expect(await response.json()).toEqual({ message: 'File size exceeds allowed file size limit (256 MB).' });
    });

    test('POST rejects empty file', async ({ request }) => {

        // try to post an empty file
        const file_name = 'empty_file.ifc';
        const empty_buffer = Buffer.alloc(0, 0); // 0 bytes of dummy data
        const file = new File([empty_buffer], file_name);
        const form = new FormData();
        form.append('file', file);
        form.append('file_name', file_name);

        let hash = btoa(TEST_CREDENTIALS);
        const response = await request.post(`${BASE_URL}/api/validationrequest/`, {
            headers: {
                'Authorization': `Basic ${hash}`,
            },
            multipart: form
        });

        // check if the response is correct - 400 Bad Request
        expect(response.statusText()).toBe('Bad Request');
        expect(response.status()).toBe(400); 
        expect(await response.json()).toEqual({ file: [ 'The submitted file is empty.' ] });
    });

    test('POST rejects empty file name', async ({ request }) => {

        // try to post a file with empty filename
        const file_name = '';
        const file_path = 'e2e/fixtures/valid_file.ifc'; // valid content
        const file = new File([readFileSync(file_path)], file_name);
        const form = new FormData();
        form.append('file', file);
        form.append('file_name', file_name);

        let hash = btoa(TEST_CREDENTIALS);
        const response = await request.post(`${BASE_URL}/api/validationrequest/`, {
            headers: {
                'Authorization': `Basic ${hash}`,
            },
            multipart: form
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

        // try to post a file with invalid filename/ext
        const file_name = 'invalid_file';
        const file_path = 'e2e/fixtures/valid_file.ifc'; // valid content
        const file = new File([readFileSync(file_path)], file_name);
        const form = new FormData();
        form.append('file', file);
        form.append('file_name', file_name);

        let hash = btoa(TEST_CREDENTIALS);
        const response = await request.post(`${BASE_URL}/api/validationrequest/`, {
            headers: {
                'Authorization': `Basic ${hash}`,
            },
            multipart: form
        });

        // check if the response is correct - 400 Bad Request
        expect(response.statusText()).toBe('Bad Request');
        expect(response.status()).toBe(400); 
        expect(await response.json()).toEqual({ file_name: "File name must end with '.ifc'." });
    });

    test('POST only accepts a single file (for now)', async ({ request }) => {

        // try to post two valid files
        const file_path = 'e2e/fixtures/valid_file.ifc';
        const file_name = basename(file_path);
        const file = new File([readFileSync(file_path)], file_name);
        const form = new FormData();
        form.append('file', file);
        form.append('file_name', file_name);
        form.append('file', file);
        form.append('file_name', file_name);

        let hash = btoa(TEST_CREDENTIALS);
        const response = await request.post(`${BASE_URL}/api/validationrequest/`, {
            headers: {
                'Authorization': `Basic ${hash}`,
            },
            multipart: form
        });

        // check if the response is correct - 400 Bad Request
        expect(response.statusText()).toBe('Bad Request');
        expect(response.status()).toBe(400); 
        expect(await response.json()).toEqual({ message: 'Only one file can be uploaded at a time.' });
    });

    test('GET returns a list', async ({ request }) => {

        // try to post a valid file
        const file_path = 'e2e/fixtures/valid_file.ifc';
        const file_name = basename(file_path);
        const file = new File([readFileSync(file_path)], file_name);
        const form = new FormData();
        form.append('file', file);
        form.append('file_name', file_name);

        let hash = btoa(TEST_CREDENTIALS);
        let response = await request.post(`${BASE_URL}/api/validationrequest/`, {
            headers: {
                'Authorization': `Basic ${hash}`,
            },
            multipart: form
        });

        // retrieve list of ValidationRequests
        response = await request.get(`${BASE_URL}/api/validationrequest`, {
            headers: {
                'Authorization': `Basic ${hash}`,
            }
        });

        // check if the response is correct - 200 OK
        expect(response.statusText()).toBe('OK');
        expect(response.status()).toBe(200);
        const data = await response.json();
        expect(data).toBeInstanceOf(Array);
        expect(data.length).toBeGreaterThan(0);
        expect(data[0]).toHaveProperty('public_id');
        expect(data[0]).toHaveProperty('file_name');
    });

    test('GET without trailing slash returns a list', async ({ request }) => {

        // try to post a valid file
        const file_path = 'e2e/fixtures/valid_file.ifc';
        const file_name = basename(file_path);
        const file = new File([readFileSync(file_path)], file_name);
        const form = new FormData();
        form.append('file', file);
        form.append('file_name', file_name);

        let hash = btoa(TEST_CREDENTIALS);
        let response = await request.post(`${BASE_URL}/api/validationrequest`, {
            headers: {
                'Authorization': `Basic ${hash}`,
            },
            multipart: form
        });

        // retrieve list of ValidationRequests
        response = await request.get(`${BASE_URL}/api/validationrequest`, {
            headers: {
                'Authorization': `Basic ${hash}`,
            }
        });

        // check if the response is correct - 200 OK
        expect(response.statusText()).toBe('OK');
        expect(response.status()).toBe(200);
        const data = await response.json();
        expect(data).toBeInstanceOf(Array);
        expect(data.length).toBeGreaterThan(0);
        expect(data[0]).toHaveProperty('public_id');
        expect(data[0]).toHaveProperty('file_name');
    });

    test('PUT is not supported', async ({ request }) => {

        // try to post a valid file
        const file_path = 'e2e/fixtures/valid_file.ifc';
        const file_name = basename(file_path);
        const file = new File([readFileSync(file_path)], file_name);
        const form = new FormData();
        form.append('file', file);
        form.append('file_name', file_name);

        let hash = btoa(TEST_CREDENTIALS);
        const response = await request.put(`${BASE_URL}/api/validationrequest/`, {
            headers: {
                'Authorization': `Basic ${hash}`,
            },
            multipart: form
        });

        // check if the response is correct - 405 Method Not allowed
        expect(response.statusText()).toBe('Method Not Allowed');
        expect(response.status()).toBe(405); 
        expect(await response.json()).toEqual({ detail: 'Method \"PUT\" not allowed.' });
    });

});