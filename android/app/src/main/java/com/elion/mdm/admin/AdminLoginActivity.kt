package com.elion.mdm.admin

import android.content.Intent
import android.os.Bundle
import android.os.CountDownTimer
import android.view.View
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.elion.mdm.R
import com.elion.mdm.security.AdminAuthManager
import kotlinx.coroutines.launch

/**
 * AdminLoginActivity — tela de autenticação do administrador.
 *
 * NUNCA expõe configurações sem autenticação prévia.
 * Protegida contra brute-force via AdminAuthManager.
 */
class AdminLoginActivity : AppCompatActivity() {

    companion object {
        private const val TAG = "ElionAdminLogin"
    }

    private lateinit var authManager: AdminAuthManager

    private lateinit var etEmail: EditText
    private lateinit var etPassword: EditText
    private lateinit var tvError: TextView
    private lateinit var tvAttempts: TextView
    private lateinit var btnLogin: Button
    private lateinit var btnBack: TextView
    private lateinit var progressBar: ProgressBar

    private var lockoutTimer: CountDownTimer? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_admin_login)

        authManager = AdminAuthManager(this)

        bindViews()
        setupListeners()
        checkLockout()
    }

    override fun onDestroy() {
        super.onDestroy()
        lockoutTimer?.cancel()
    }

    private fun bindViews() {
        etEmail     = findViewById(R.id.et_email)
        etPassword  = findViewById(R.id.et_password)
        tvError     = findViewById(R.id.tv_error)
        tvAttempts  = findViewById(R.id.tv_attempts)
        btnLogin    = findViewById(R.id.btn_login)
        btnBack     = findViewById(R.id.btn_back)
        progressBar = findViewById(R.id.progress_bar)
    }

    private fun setupListeners() {
        btnLogin.setOnClickListener { attemptLogin() }
        btnBack.setOnClickListener { finish() }
    }

    private fun attemptLogin() {
        val email = etEmail.text.toString().trim()
        val password = etPassword.text.toString().trim()

        if (email.isBlank() || password.isBlank()) {
            showError("Preencha email e senha")
            return
        }

        setLoading(true)

        lifecycleScope.launch {
            val result = authManager.authenticate(email, password)

            setLoading(false)

            when (result) {
                is AdminAuthManager.AuthResult.Success -> {
                    // Sucesso — action específica ou painel admin?
                    hideError()
                    val action = intent.getStringExtra("EXTRA_ACTION")
                    if (action == "ACTION_APP_SELECTION") {
                        setResult(android.app.Activity.RESULT_OK)
                        finish()
                    } else {
                        startActivity(Intent(this@AdminLoginActivity, AdminPanelActivity::class.java))
                        finish()
                    }
                }

                is AdminAuthManager.AuthResult.Failed -> {
                    showError("Credenciais inválidas")
                    showAttempts(result.remainingAttempts)
                }

                is AdminAuthManager.AuthResult.LockedOut -> {
                    showError("Conta bloqueada por excesso de tentativas")
                    startLockoutCountdown(result.remainingSeconds)
                }
            }
        }
    }

    private fun checkLockout() {
        if (authManager.isLockedOut()) {
            val remaining = authManager.getRemainingLockoutSeconds()
            showError("Conta bloqueada por excesso de tentativas")
            startLockoutCountdown(remaining)
        }
    }

    private fun startLockoutCountdown(seconds: Long) {
        btnLogin.isEnabled = false
        etEmail.isEnabled = false
        etPassword.isEnabled = false

        lockoutTimer?.cancel()
        lockoutTimer = object : CountDownTimer(seconds * 1000, 1000) {
            override fun onTick(millisUntilFinished: Long) {
                val secs = millisUntilFinished / 1000
                tvAttempts.text = "Aguarde ${secs}s para tentar novamente"
                tvAttempts.visibility = View.VISIBLE
            }

            override fun onFinish() {
                btnLogin.isEnabled = true
                etEmail.isEnabled = true
                etPassword.isEnabled = true
                tvAttempts.visibility = View.GONE
                hideError()
            }
        }.start()
    }

    private fun showError(message: String) {
        tvError.text = message
        tvError.visibility = View.VISIBLE
    }

    private fun hideError() {
        tvError.visibility = View.GONE
    }

    private fun showAttempts(remaining: Int) {
        tvAttempts.text = "$remaining tentativa(s) restante(s)"
        tvAttempts.visibility = View.VISIBLE
    }

    private fun setLoading(loading: Boolean) {
        progressBar.visibility = if (loading) View.VISIBLE else View.GONE
        btnLogin.isEnabled = !loading
        etEmail.isEnabled = !loading
        etPassword.isEnabled = !loading
    }
}
