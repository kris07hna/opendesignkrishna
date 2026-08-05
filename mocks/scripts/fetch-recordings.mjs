import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
import https from 'https';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
// Note: when run from C:\Users\krish\open-design, MOCKS_DIR is C:\Users\krish\open-design\mocks
const MOCKS_DIR = path.resolve('mocks');
const MANIFEST_PATH = path.join(MOCKS_DIR, 'manifest.json');
const RECORDINGS_DIR = path.join(MOCKS_DIR, 'recordings');

// Create recordings directory if not exists
if (!fs.existsSync(RECORDINGS_DIR)) {
    fs.mkdirSync(RECORDINGS_DIR, { recursive: true });
}

function computeSha256(filePath) {
    if (!fs.existsSync(filePath)) return '';
    const fileBuffer = fs.readFileSync(filePath);
    const hashSum = crypto.createHash('sha256');
    hashSum.update(fileBuffer);
    return hashSum.digest('hex');
}

function downloadFile(url, destPath) {
    return new Promise((resolve, reject) => {
        const tempPath = destPath + '.tmp';
        const file = fs.createWriteStream(tempPath);
        https.get(url, (response) => {
            if (response.statusCode !== 200) {
                reject(new Error(`Failed to download ${url}: HTTP Status ${response.statusCode}`));
                return;
            }
            response.pipe(file);
            file.on('finish', () => {
                file.close();
                resolve(tempPath);
            });
        }).on('error', (err) => {
            fs.unlink(tempPath, () => {});
            reject(err);
        });
    });
}

async function main() {
    try {
        console.log(`Reading manifest from ${MANIFEST_PATH}...`);
        const manifest = JSON.parse(fs.readFileSync(MANIFEST_PATH, 'utf-8'));
        const publicUrlBase = manifest.storage.public_url_base;
        const objectPrefix = manifest.storage.object_prefix;
        const entries = manifest.entries;

        console.log(`Found ${entries.length} entries in manifest.`);
        console.log(`Starting downloads (concurrency = 8)...`);

        const CONCURRENCY = 8;
        let index = 0;
        let downloadedCount = 0;
        let skippedCount = 0;
        let failedCount = 0;

        async function worker() {
            while (index < entries.length) {
                const entry = entries[index++];
                const traceId = entry.trace_id;
                const expectedSha = entry.sha256;
                const filename = `${traceId}.jsonl`;
                const destPath = path.join(RECORDINGS_DIR, filename);
                const fileUrl = `${publicUrlBase}/${objectPrefix}${filename}`;

                // Check existing file hash
                if (fs.existsSync(destPath)) {
                    const currentSha = computeSha256(destPath);
                    if (currentSha === expectedSha) {
                        skippedCount++;
                        continue;
                    }
                }

                try {
                    const tempPath = await downloadFile(fileUrl, destPath);
                    const downloadedSha = computeSha256(tempPath);
                    if (downloadedSha !== expectedSha) {
                        throw new Error(`SHA256 mismatch for ${traceId}: expected ${expectedSha}, got ${downloadedSha}`);
                    }
                    fs.renameSync(tempPath, destPath);
                    downloadedCount++;
                    if (downloadedCount % 10 === 0) {
                        console.log(`Progress: Downloaded ${downloadedCount}, Skipped ${skippedCount}, Failed ${failedCount}`);
                    }
                } catch (err) {
                    console.error(`Error downloading ${traceId}: ${err.message}`);
                    failedCount++;
                }
            }
        }

        const workers = Array.from({ length: CONCURRENCY }, () => worker());
        await Promise.all(workers);

        console.log('\n--- Sync Complete ---');
        console.log(`✓ Newly downloaded: ${downloadedCount}`);
        console.log(`• Already cached:   ${skippedCount}`);
        console.log(`✗ Failed:           ${failedCount}`);
        if (failedCount > 0) {
            process.exit(1);
        }
    } catch (err) {
        console.error('Fatal error:', err);
        process.exit(1);
    }
}

main();
