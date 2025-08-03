import { test, expect } from '@playwright/test';
import { readFileSync } from 'fs';
import { basename } from 'path';

const BASE_URL = 'http://localhost:8000';
const TEST_CREDENTIALS = 'root:root';

function createAuthHeader(credentials) {

    const hash = Buffer.from(credentials).toString('base64');
    return {
        'Authorization': `Basic ${hash}`
    };
}

function createFormData(filePath) {

    const fileName = basename(filePath);
    const file = new File([readFileSync(filePath)], fileName);
    const form = new FormData();
    form.append('file', file);
    form.append('file_name', fileName);
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
            multipart: createFormData('e2e/fixtures/valid_file.ifc')
        });

        // check if the response is correct - 201 Created
        expect(response.statusText()).toBe('Created');
        expect(response.status()).toBe(201);
    });

    test('POST without trailing slash accepts valid file', async ({ request }) => {

        // try to post a valid file
        const response = await request.post(`${BASE_URL}/api/validationrequest`, {
            headers: createAuthHeader(TEST_CREDENTIALS),
            multipart: createFormData('e2e/fixtures/valid_file.ifc')
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
        expect(await response.json()).toEqual({ message: 'File size exceeds allowed file size limit (256 MB).' });
    });

    test('GET returns a list', async ({ request }) => {

        // post a valid file
        let response = await request.post(`${BASE_URL}/api/validationrequest/`, {
            headers: createAuthHeader(TEST_CREDENTIALS),
            multipart: createFormData('e2e/fixtures/valid_file.ifc')
        });

        // retrieve list of ValidationRequests
        response = await request.get(`${BASE_URL}/api/validationrequest/`, {
            headers: createAuthHeader(TEST_CREDENTIALS)
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

        // post a valid file
        let response = await request.post(`${BASE_URL}/api/validationrequest/`, {
            headers: createAuthHeader(TEST_CREDENTIALS),
            multipart: createFormData('e2e/fixtures/valid_file.ifc')
        });

        // retrieve list of ValidationRequests
        response = await request.get(`${BASE_URL}/api/validationrequest`, {
            headers: createAuthHeader(TEST_CREDENTIALS)
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

});