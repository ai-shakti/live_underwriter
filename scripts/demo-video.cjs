/**
 * Live Underwriter — Playwright Demo Video Script
 *
 * Records a ~90-second demo showcasing:
 * 1. Landing page with sample applicants
 * 2. Clean application → ACCEPT (Jane Doe)
 * 3. Flagged application → REVIEW with human-in-the-loop (Maria Garcia)
 * 4. Audit trail with explainability
 * 5. Reviews dashboard
 *
 * Usage:
 *   node scripts/demo-video.cjs
 *
 * Requires:
 *   - Backend running on http://localhost:8000
 *   - Frontend running on http://localhost:5173
 *   - Playwright installed (npm install playwright)
 *   - ffmpeg installed (brew install ffmpeg)
 */

const { chromium } = require("playwright");
const { execSync, spawn } = require("child_process");
const { existsSync, mkdirSync, readdirSync, statSync } = require("fs");
const { resolve } = require("path");

const OUTPUT_DIR = resolve(__dirname, "../demo-output");
const VIDEO_PATH = resolve(OUTPUT_DIR, "live-underwriter-demo.mp4");

// Ensure output directory exists
if (!existsSync(OUTPUT_DIR)) mkdirSync(OUTPUT_DIR, { recursive: true });

const FRONTEND_URL = "http://localhost:5173";
const BACKEND_URL = "http://localhost:8000";

/** Wait for a server to be ready */
async function waitForServer(url, label, timeoutMs = 30000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const resp = await fetch(url);
      if (resp.ok) {
        console.log(`  ✓ ${label} is ready`);
        return;
      }
    } catch {}
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`${label} did not start within ${timeoutMs}ms`);
}

/** Type text slowly for a natural demo feel */
async function slowType(page, selector, text, delay = 30) {
  await page.click(selector);
  await page.fill(selector, "");
  for (const char of text) {
    await page.type(selector, char, { delay });
  }
}

/** Pause for dramatic effect */
function beat(ms = 800) {
  return new Promise((r) => setTimeout(r, ms));
}

async function main() {
  console.log("\n🎬 Live Underwriter Demo Video Generator\n");
  console.log("Checking servers...");

  // Check if servers are running
  try {
    await waitForServer(`${BACKEND_URL}/api/health`, "Backend API");
  } catch {
    console.log("  Starting backend server...");
    const backend = spawn("uv", ["run", "live-underwriter-api"], {
      cwd: resolve(__dirname, "../backend"),
      stdio: "pipe",
      shell: true,
    });
    backend.stdout.on("data", (d) => process.stdout.write(d));
    backend.stderr.on("data", (d) => process.stderr.write(d));
    await waitForServer(`${BACKEND_URL}/api/health`, "Backend API", 60000);
  }

  try {
    await waitForServer(FRONTEND_URL, "Frontend");
  } catch {
    console.log("  Starting frontend server...");
    const frontend = spawn("npx", ["vite", "--host"], {
      cwd: resolve(__dirname, "../frontend"),
      stdio: "pipe",
      shell: true,
    });
    frontend.stdout.on("data", (d) => process.stdout.write(d));
    frontend.stderr.on("data", (d) => process.stderr.write(d));
    await waitForServer(FRONTEND_URL, "Frontend", 60000);
  }

  // Seed the database with synthetic data
  console.log("\n  Seeding database...");
  try {
    execSync("uv run python -m live_underwriter.data_generator --count 20 --seed-db", {
      cwd: resolve(__dirname, "../backend"),
      stdio: "pipe",
    });
    console.log("  ✓ Database seeded");
  } catch (e) {
    console.log("  ⚠ Seed may have failed, continuing...");
  }

  // Launch browser with video recording
  console.log("\n🚀 Launching browser...");
  const browser = await chromium.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    recordVideo: { dir: OUTPUT_DIR, size: { width: 1440, height: 900 } },
    deviceScaleFactor: 2,
  });

  const page = await context.newPage();

  try {
    // ===================================================================
    // SCENE 1: Landing Page
    // ===================================================================
    console.log("\n📋 Scene 1: Landing page overview");
    await page.goto(FRONTEND_URL, { waitUntil: "networkidle" });
    await beat(1500);

    // ===================================================================
    // SCENE 2: Select Jane Doe (clean applicant → ACCEPT)
    // ===================================================================
    console.log("\n✅ Scene 2: Clean application — Jane Doe → ACCEPT");

    // Select Jane Doe from the sample dropdown
    await page.selectOption('select:has(option[value="jane-doe"])', "jane-doe");
    await beat(1000);

    // Click "Run Underwriting"
    await page.click('button:has-text("Run Underwriting")');
    await beat(3000);

    // Wait for results to appear
    await page.waitForSelector('text=ACCEPT', { timeout: 30000 }).catch(() => {});
    await beat(2000);

    // ===================================================================
    // SCENE 3: Show the audit trail
    // ===================================================================
    console.log("\n📝 Scene 3: Audit trail explainability");

    // Scroll to show the full result
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await beat(1000);

    // Take a full-page screenshot for reference
    await page.screenshot({ path: resolve(OUTPUT_DIR, "scene-3-audit-trail.png"), fullPage: true });
    await beat(1000);

    // ===================================================================
    // SCENE 4: Maria Garcia (flagged → human review)
    // ===================================================================
    console.log("\n⚠️  Scene 4: Flagged application — Maria Garcia → REVIEW");

    // Scroll back up
    await page.evaluate(() => window.scrollTo(0, 0));
    await beat(500);

    // Select Maria Garcia
    await page.selectOption('select:has(option[value="maria-garcia"])', "maria-garcia");
    await beat(1000);

    // Run underwriting
    await page.click('button:has-text("Run Underwriting")');
    await beat(3000);

    // Wait for results
    await page.waitForSelector('text=REVIEW', { timeout: 30000 }).catch(() => {});
    await beat(2000);

    // Scroll to see flags
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await beat(1500);

    // ===================================================================
    // SCENE 5: Reviews dashboard (human-in-the-loop)
    // ===================================================================
    console.log("\n👤 Scene 5: Human-in-the-loop reviews dashboard");

    // Scroll to reviews section
    const reviewsSection = await page.$('text=Pending Reviews');
    if (reviewsSection) {
      await reviewsSection.scrollIntoViewIfNeeded();
      await beat(1000);

      // Click "Approve" on the first pending review
      const approveBtn = await page.$('button:has-text("Approve")');
      if (approveBtn) {
        await approveBtn.click();
        await beat(1500);
      }
    }

    // ===================================================================
    // SCENE 6: CLI demo (run in terminal, show output)
    // ===================================================================
    console.log("\n💻 Scene 6: CLI demo with --audit flag");

    // Run the CLI command and capture output
    const cliOutput = execSync(
      `uv run live-underwriter --transcript "My name is Jane Doe, born 1985-04-12, policy POL-1001, coverage 500000, income 120000" --audit`,
      {
        cwd: resolve(__dirname, "../backend"),
        encoding: "utf-8",
        timeout: 30000,
      }
    );
    console.log(cliOutput);

    // Take a final screenshot
    await page.screenshot({ path: resolve(OUTPUT_DIR, "scene-6-final.png"), fullPage: true });
    await beat(1000);

    console.log("\n✅ Demo complete! Processing video...");

  } catch (err) {
    console.error("\n❌ Error during demo:", err.message);
  } finally {
    // Close browser — this finalizes the video file
    await context.close();
    await browser.close();
  }

  // ===================================================================
  // Post-process: Convert WebM to MP4 with ffmpeg
  // ===================================================================
  console.log("\n🎞️  Converting video to MP4...");

  // Find the recorded video file
  const files = readdirSync(OUTPUT_DIR);
  const webmFile = files.find((f) => f.endsWith(".webm"));

  if (webmFile) {
    const webmPath = resolve(OUTPUT_DIR, webmFile);
    try {
      execSync(
        `ffmpeg -i "${webmPath}" \
          -c:v libx264 \
          -preset medium \
          -crf 22 \
          -pix_fmt yuv420p \
          -vf "scale=1080:trunc(ow/a/2)*2" \
          -movflags +faststart \
          -c:a aac \
          -b:a 128k \
          "${VIDEO_PATH}" \
          -y`,
        { stdio: "pipe", timeout: 60000 }
      );
      console.log(`  ✓ Video saved to: ${VIDEO_PATH}`);

      // Also create a smaller version for social media
      const socialPath = resolve(OUTPUT_DIR, "live-underwriter-social.mp4");
      execSync(
        `ffmpeg -i "${VIDEO_PATH}" \
          -c:v libx264 \
          -preset fast \
          -crf 28 \
          -vf "scale=720:trunc(ow/a/2)*2" \
          -c:a aac \
          -b:a 96k \
          -t 90 \
          "${socialPath}" \
          -y`,
        { stdio: "pipe", timeout: 60000 }
      );
      console.log(`  ✓ Social media version: ${socialPath}`);

      // Get file sizes
      const mainSize = (statSync(VIDEO_PATH).size / 1024 / 1024).toFixed(1);
      const socialSize = (statSync(socialPath).size / 1024 / 1024).toFixed(1);
      console.log(`  📦 Full video: ${mainSize} MB`);
      console.log(`  📦 Social video: ${socialSize} MB`);

    } catch (e) {
      console.error("  ⚠ Video conversion failed:", e.message);
      console.log(`  Raw video at: ${webmPath}`);
    }
  } else {
    console.log("  ⚠ No video file found in output directory");
  }

  console.log("\n✨ Done! Check the demo-output/ folder for your videos.\n");
}

main().catch(console.error);
