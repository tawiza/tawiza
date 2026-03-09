import { test, expect } from '@playwright/test';

test('Homepage has correct title', async ({ page }) => {
  await page.goto('/');

  // Vérifiez le titre - adaptez ceci au titre réel de votre application
  // await expect(page).toHaveTitle(/Tawiza/); 
  
  // Test générique pour vérifier que la page charge
  await expect(page).not.toHaveTitle(/404/);
});
