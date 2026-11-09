const { test, expect } = require('@playwright/test');

const baseUrl = process.env.SEI_BASE_URL || 'https://treinamento.sei.sp.gov.br';
const orgao = process.env.SEI_ORGAO || 'GESP-TREINAMENTO';
const usuario = process.env.SEI_USUARIO;
const senha = process.env.SEI_SENHA;
const loginRealDisponivel = Boolean(usuario && senha && usuario !== 'SEU_USUARIO' && senha !== 'SUA_SENHA');

test('login no SEI', async ({ page }) => {
  test.skip(!loginRealDisponivel, 'Defina as variáveis SEI_USUARIO e SEI_SENHA para executar o login real do SEI.');

  const loginUrl = `${baseUrl}/sip/login.php?sigla_orgao_sistema=${encodeURIComponent(orgao)}&sigla_sistema=SEI&infra_url=L3NlaS8=`;

  await page.goto(loginUrl);
  await page.waitForLoadState('domcontentloaded');

  const campoUsuario = page.getByLabel('Usuário').or(page.locator('input[name="txtUsuario"], input[name="usuario"], input[id*="usuario"], input[type="text"]').first());
  const campoSenha = page.locator('input#pwdSenha');
  const botaoEntrar = page.getByRole('button', { name: /ACESSAR|Entrar/i }).or(page.locator('input[type="submit"], button[type="submit"]').first());

  await expect(campoUsuario).toBeVisible({ timeout: 20000 });
  await expect(campoSenha).toBeVisible({ timeout: 20000 });

  await campoUsuario.fill(usuario);
  await campoSenha.fill(senha);

  const selectOrgao = page.locator('select').first();
  if (await selectOrgao.count()) {
    const valorAtual = await selectOrgao.inputValue();
    if (!valorAtual || valorAtual !== orgao) {
      await selectOrgao.selectOption({ label: orgao }).catch(async () => {
        await selectOrgao.selectOption({ value: orgao }).catch(() => {});
      });
    }
  }

  await botaoEntrar.click();

  await expect(page).not.toHaveURL(/\/sip\/login\.php(?:[?#]|$)/i, { timeout: 15000 });
  await expect(page.getByLabel('Usuário')).toBeHidden({ timeout: 30000 });

  await page.screenshot({ path: 'sei-login-sucesso.png', fullPage: true });

  console.log('Login do SEI executado. Verifique o screenshot e a URL final.');
});