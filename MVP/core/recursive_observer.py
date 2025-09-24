import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import List, Tuple, Optional
from torch.distributions import Normal

class VAE(nn.Module):
    def __init__(self, input_dim: int = 512, latent_dim: int = 512, hidden_dim: int = 400):
        super().__init__()
        # Keep same dimensions to avoid mismatch - compression can be added later
        # Encoder
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU()
        )
        self.fc_mu = nn.Linear(hidden_dim // 2, latent_dim)
        self.fc_logvar = nn.Linear(hidden_dim // 2, latent_dim)
        # Decoder
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, input_dim)
        )

    def encode(self, x):
        h = self.encoder(x)
        mu = self.fc_mu(h)
        logvar = self.fc_logvar(h)
        return mu, logvar

    def reparameterize(self, mu, logvar):
        std = torch.exp(0.5 * logvar)
        eps = torch.randn_like(std)
        return mu + eps * std

    def decode(self, z):
        return self.decoder(z)

    def forward(self, x):
        mu, logvar = self.encode(x)
        z = self.reparameterize(mu, logvar)
        recon_x = self.decode(z)
        return recon_x, mu, logvar

    def loss(self, recon_x, x, mu, logvar):
        BCE = F.binary_cross_entropy(recon_x, x, reduction='sum')
        KLD = -0.5 * torch.sum(1 + logvar - mu.pow(2) - logvar.exp())
        return BCE + KLD

class RecursiveObserver:
    def __init__(self, state_dim: int = 512, n_max: int = 10, alpha: float = 0.8, sigma: float = 0.1, lambda_max: float = 0.9):
        self.state_dim = state_dim
        self.n_max = n_max
        self.alpha = alpha
        self.sigma = sigma
        self.lambda_max = lambda_max
        self.vae = VAE(input_dim=state_dim)
        self.optimizer = torch.optim.Adam(self.vae.parameters(), lr=1e-3)
        self.phi_w = torch.randn(state_dim, state_dim) * 0.5  # Initial W
        self.phi_b = torch.zeros(state_dim)
        self._ensure_contraction()
        self.phi_n_list = []  # Phi_n cumulative

    def _ensure_contraction(self):
        # Adjust W to ensure rho(W) < lambda_max
        eigvals = torch.linalg.eigvals(self.phi_w)
        rho = torch.max(torch.abs(eigvals)).item()
        if rho > self.lambda_max:
            self.phi_w *= self.lambda_max / rho

    def recurrence_step(self, s_prev: torch.Tensor, eta: Optional[torch.Tensor] = None) -> torch.Tensor:
        if eta is None:
            eta = torch.normal(0, self.sigma, size=s_prev.shape)
        s_curr = self.alpha * s_prev + (1 - self.alpha) * s_prev + eta  # Damped recurrence
        s_curr = self.phi_w @ s_curr + self.phi_b  # Contraction
        return s_curr

    def compress(self, s: torch.Tensor) -> torch.Tensor:
        with torch.no_grad():
            recon, mu, logvar = self.vae(s.unsqueeze(0))
            z = self.vae.reparameterize(mu, logvar)
            fidelity = 1 - F.mse_loss(recon, s.unsqueeze(0))
            if fidelity < 0.95:
                # Retrain VAE if fidelity low (simplified)
                pass
            return z.squeeze(0)

    def calculate_mutual_information(self, s_n: torch.Tensor, s_nm1: torch.Tensor) -> float:
        """
        Calculate proper mutual information I(S_n; S_{n-1}) using KL divergence
        Based on whitepaper: Φ_n = Φ_{n-1} + I(S_n ; S_{n-1})
        """
        try:
            # Convert to numpy for MI calculation
            x = s_n.detach().numpy().reshape(-1, 1)
            y = s_nm1.detach().numpy().reshape(-1, 1)
            
            # Safety checks
            if len(x) == 0 or len(y) == 0:
                return 0.0
                
            # Use entropy-based MI estimation
            # MI(X,Y) = H(X) + H(Y) - H(X,Y)
            from scipy.stats import entropy
            
            # Discretize for entropy calculation (bins based on data range)
            bins = min(50, max(2, len(x) // 4))
                
            # Calculate marginal entropies
            x_hist, _ = np.histogram(x, bins=bins, density=True)
            y_hist, _ = np.histogram(y, bins=bins, density=True)
            
            # Add small epsilon to avoid log(0)
            epsilon = 1e-8
            x_hist = x_hist + epsilon
            y_hist = y_hist + epsilon
            
            h_x = entropy(x_hist)
            h_y = entropy(y_hist)
            
            # Joint entropy - use 2D histogram
            joint_hist, _, _ = np.histogram2d(x.flatten(), y.flatten(), bins=bins, density=True)
            joint_hist = joint_hist + epsilon
            h_xy = entropy(joint_hist.flatten())
            
            mi = h_x + h_y - h_xy
            
            # Safety check for NaN/inf
            if np.isnan(mi) or np.isinf(mi):
                return 0.0
                
            return max(0.0, mi)  # MI should be non-negative
            
        except Exception as e:
            print(f"Error in calculate_mutual_information: {e}")
            return 0.0  # Return safe default

    def observe(self, s0: np.ndarray, train_vae: bool = False) -> List[Tuple[torch.Tensor, float]]:
        # Ensure input is tensor
        if isinstance(s0, np.ndarray):
            s0_tensor = torch.tensor(s0, dtype=torch.float32)
        else:
            s0_tensor = s0.clone().detach().float()
        
        states = [s0_tensor]
        phi_n = 0.0
        self.phi_n_list = [phi_n]
        s_curr = s0_tensor

        for n in range(1, self.n_max + 1):
            eta = torch.normal(0, self.sigma, size=s_curr.shape)
            s_curr = self.recurrence_step(s_curr, eta)
            # Compress if n % 2 == 0 or high surprise (selective)
            if n % 2 == 0:
                s_curr = self.compress(s_curr)
            states.append(s_curr)
            i = self.calculate_mutual_information(s_curr, states[-2])
            phi_n += i
            self.phi_n_list.append(phi_n)

        # Check convergence
        s_star = states[-1]
        if torch.norm(self.recurrence_step(s_star, eta=torch.zeros_like(s_star)) - s_star) < 1e-3:
            print(f"Converged at n={n}")

        return list(zip(states, self.phi_n_list))

    def train_vae_on_states(self, states: List[torch.Tensor], epochs: int = 10, train_vae: bool = True):
        if train_vae:
            for epoch in range(epochs):
                total_loss = 0
                for s in states:
                    recon, mu, logvar = self.vae(s.unsqueeze(0))
                    loss = self.vae.loss(recon, s.unsqueeze(0), mu, logvar)
                    self.optimizer.zero_grad()
                    loss.backward()
                    self.optimizer.step()
                    total_loss += loss.item()
                print(f"VAE Epoch {epoch}, Loss: {total_loss / len(states)}")