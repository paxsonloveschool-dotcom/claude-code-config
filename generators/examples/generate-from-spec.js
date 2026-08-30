#!/usr/bin/env node

import Anthropic from "@anthropic-ai/sdk";
import fs from "fs";
import path from "path";
import { execSync } from "child_process";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const client = new Anthropic();

/**
 * Generate a React component from a spec file
 * Usage: node generate-from-spec.js <spec-file.md> <ComponentName>
 */

async function generateFromSpecFile(specFile, componentName) {
  if (!fs.existsSync(specFile)) {
    console.error(`❌ Spec file not found: ${specFile}`);
    process.exit(1);
  }

  const spec = fs.readFileSync(specFile, "utf-8");
  console.log(`📖 Read specification from ${specFile}`);

  const componentDir = path.join(__dirname, "..", "generated", componentName);
  const componentFile = path.join(componentDir, `${componentName}.jsx`);
  const testFile = path.join(componentDir, `${componentName}.test.jsx`);

  fs.mkdirSync(componentDir, { recursive: true });

  let attempt = 0;
  let lastError = null;
  const maxRetries = 3;

  while (attempt < maxRetries) {
    attempt++;
    console.log(
      `\n📝 Attempt ${attempt}/${maxRetries}: Generating ${componentName}...`
    );

    const prompt = buildPrompt(spec, componentName, lastError);

    try {
      const message = await client.messages.create({
        model: "claude-opus-4-1-20250805",
        max_tokens: 2048,
        messages: [
          {
            role: "user",
            content: prompt,
          },
        ],
      });

      const responseText =
        message.content[0].type === "text" ? message.content[0].text : "";

      // Extract component code
      const componentMatch = responseText.match(/```jsx\n([\s\S]*?)\n```/);
      if (!componentMatch) {
        throw new Error("No JSX code block found in response");
      }

      const componentCode = componentMatch[1];

      // Extract test code
      const remainingText = responseText.substring(
        componentMatch.index + componentMatch[0].length
      );
      const testMatch = remainingText.match(/```jsx\n([\s\S]*?)\n```/);
      const testCode = testMatch ? testMatch[1] : generateDefaultTest(componentName);

      fs.writeFileSync(componentFile, componentCode);
      fs.writeFileSync(testFile, testCode);

      console.log(`✅ Component written to ${componentFile}`);
      console.log(`✅ Tests written to ${testFile}`);

      console.log("\n🧪 Running tests...");
      try {
        execSync(`npm test -- ${componentName}.test.jsx`, {
          cwd: path.join(__dirname, ".."),
          stdio: "inherit",
        });
        console.log(`\n✨ All tests passed for ${componentName}!`);
        return { success: true, componentFile, testFile };
      } catch (testError) {
        lastError = extractTestError(testError);
        console.error(`\n❌ Tests failed:\n${lastError}`);

        if (attempt < maxRetries) {
          console.log(`\n🔄 Retrying with error feedback...\n`);
        }
      }
    } catch (error) {
      lastError = error.message;
      console.error(`\n❌ Generation error: ${lastError}`);

      if (attempt < maxRetries) {
        console.log(`\n🔄 Retrying...\n`);
      }
    }
  }

  return {
    success: false,
    error: `Failed to generate ${componentName} after ${maxRetries} attempts. Last error: ${lastError}`,
  };
}

function buildPrompt(spec, componentName, previousError) {
  let prompt = `Generate a React component based on this specification:

${spec}

Requirements:
1. Write production-ready React code
2. Use React hooks (useState, useEffect, useCallback, etc.)
3. Include comprehensive JSDoc comments
4. Handle all edge cases mentioned in the spec
5. Follow React best practices and conventions
6. Export as default export
7. Make it fully testable

Return the component code in a \`\`\`jsx block.

Then provide comprehensive Jest tests in another \`\`\`jsx block that test:
- All mentioned features and variants
- All edge cases
- User interactions
- Props validation
- Accessibility requirements

Format:
\`\`\`jsx
// Component code
\`\`\`

\`\`\`jsx
// Test code with proper imports
\`\`\``;

  if (previousError) {
    prompt += `\n\nPrevious test failure - please fix:
${previousError}

Analyze the error and regenerate with the fix applied.`;
  }

  return prompt;
}

function extractTestError(error) {
  const output = error.toString();
  const lines = output.split("\n");
  const errorLines = lines
    .filter((l) => l.includes("FAIL") || l.includes("Error") || l.includes("●"))
    .slice(0, 15);

  return errorLines.length > 0 ? errorLines.join("\n") : output.substring(0, 800);
}

function generateDefaultTest(componentName) {
  return `import React from 'react';
import { render } from '@testing-library/react';
import ${componentName} from './${componentName}';

describe('${componentName}', () => {
  test('renders without crashing', () => {
    const { container } = render(<${componentName} />);
    expect(container).toBeInTheDocument();
  });
});
`;
}

// Main
const args = process.argv.slice(2);
if (args.length < 2) {
  console.log(
    "Usage: node generate-from-spec.js <spec-file.md> <ComponentName>"
  );
  console.log("Example: node generate-from-spec.js Button.spec.md Button");
  process.exit(1);
}

const [specFile, componentName] = args;

generateFromSpecFile(specFile, componentName).then((result) => {
  if (result.success) {
    console.log("\n🎉 Component generation successful!");

    // Commit to git
    try {
      console.log("\n📦 Committing to git...");
      execSync("git add generated/", {
        cwd: path.join(__dirname, ".."),
        stdio: "pipe",
      });
      execSync(
        `git commit -m "feat: generate ${componentName} component with tests"`,
        {
          cwd: path.join(__dirname, "../.."),
          stdio: "pipe",
        }
      );
      console.log("✅ Committed successfully!");
    } catch {
      console.log("⚠️  Git commit skipped (no changes)");
    }
  } else {
    console.error(`\n❌ ${result.error}`);
    process.exit(1);
  }
});
