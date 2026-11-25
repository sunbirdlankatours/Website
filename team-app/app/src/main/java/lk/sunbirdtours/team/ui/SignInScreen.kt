package lk.sunbirdtours.team.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable
fun SignInScreen(m: TeamModel, bar: SnackbarHostState) {
    var email by rememberSaveable { mutableStateOf("") }
    var password by rememberSaveable { mutableStateOf("") }
    var show by rememberSaveable { mutableStateOf(false) }
    val go = { if (email.isNotBlank() && password.isNotEmpty()) m.signIn(email, password) }

    Scaffold(snackbarHost = { SnackbarHost(bar) }) { pad ->
        Box(
            Modifier.fillMaxSize().padding(pad).systemBarsPadding().imePadding().verticalScroll(rememberScrollState()),
            contentAlignment = Alignment.Center,
        ) {
            Column(
                Modifier.widthIn(max = 420.dp).fillMaxWidth().padding(horizontal = 28.dp, vertical = 32.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(14.dp),
            ) {
                Box(Modifier.size(84.dp).clip(CircleShape).background(Blue), contentAlignment = Alignment.Center) {
                    Sun(56.dp)
                }
                Text("Sunbird Team", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.SemiBold, color = Navy)
                Text(
                    "Chats with travellers from the website. Sign in with the same email and password as the admin panel.",
                    style = MaterialTheme.typography.bodyMedium, color = Muted, textAlign = TextAlign.Center,
                )
                Spacer(Modifier.height(4.dp))
                OutlinedTextField(
                    value = email, onValueChange = { email = it }, label = { Text("Email") }, singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email, imeAction = ImeAction.Next),
                    shape = RoundedCornerShape(14.dp), modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = password, onValueChange = { password = it }, label = { Text("Password") }, singleLine = true,
                    visualTransformation = if (show) VisualTransformation.None else PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password, imeAction = ImeAction.Go),
                    keyboardActions = KeyboardActions(onGo = { go() }),
                    trailingIcon = { TextButton(onClick = { show = !show }) { Text(if (show) "Hide" else "Show", fontSize = 13.sp) } },
                    shape = RoundedCornerShape(14.dp), modifier = Modifier.fillMaxWidth(),
                )
                Button(
                    onClick = go, enabled = !m.busy && email.isNotBlank() && password.isNotEmpty(),
                    shape = RoundedCornerShape(48.dp), modifier = Modifier.fillMaxWidth().height(52.dp),
                ) {
                    if (m.busy) CircularProgressIndicator(Modifier.size(22.dp), color = Color.White, strokeWidth = 2.5.dp)
                    else Text("Sign in", fontWeight = FontWeight.SemiBold, fontSize = 16.sp)
                }
                Text(
                    "Forgot your password? Someone else on the team can set a new one in the admin panel, on the Team page.",
                    style = MaterialTheme.typography.bodySmall, color = Muted, textAlign = TextAlign.Center,
                )
            }
        }
    }
}
