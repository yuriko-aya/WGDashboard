<script>
import LocaleText from "@/components/text/localeText.vue";
import {fetchPost} from "@/utilities/fetch.js";
import {ref} from "vue";

export default {
	name: "newMikroTikConfiguration",
	components: {LocaleText},
	emits: ['validated'],
	setup(){
		const testing = ref(false);
		const testResult = ref(null);
		const testError = ref(null);
		const availableInterfaces = ref([]);
		
		return {testing, testResult, testError, availableInterfaces}
	},
	data(){
		return {
			mikrotikConfig: {
				MikroTikHost: "",
				MikroTikUsername: "",
				MikroTikPassword: "",
				MikroTikPort: 443,
				MikroTikUseSSL: true,
				MikroTikVerifySSL: false,
				CreateNew: false
			},
			showPassword: false
		}
	},
	watch: {
		mikrotikConfig: {
			deep: true,
			handler(){
				this.$emit('validated', this.mikrotikConfig, this.isValid)
			}
		}
	},
	computed: {
		isValid(){
			return this.mikrotikConfig.MikroTikHost.length > 0 &&
				this.mikrotikConfig.MikroTikUsername.length > 0 &&
				this.mikrotikConfig.MikroTikPassword.length > 0 &&
				this.mikrotikConfig.MikroTikPort > 0 &&
				this.mikrotikConfig.MikroTikPort <= 65535;
		}
	},
	methods: {
		async testConnection(){
			if (!this.isValid) return;
			
			this.testing = true;
			this.testResult = null;
			this.testError = null;
			this.availableInterfaces = [];
			
			await fetchPost("/api/testMikroTikConnection", this.mikrotikConfig, (res) => {
				this.testing = false;
				if (res.status){
					this.testResult = "Connection successful!";
					if (res.data && res.data.interfaces){
						this.availableInterfaces = res.data.interfaces;
					}
				}else{
					this.testError = res.message || "Connection failed";
				}
			});
		}
	}
}
</script>

<template>
	<div class="d-flex flex-column gap-3">
		<!-- Connection Type -->
		<div class="card rounded-3 shadow">
			<div class="card-header">
				<LocaleText t="Configuration Type"></LocaleText>
			</div>
			<div class="card-body d-flex gap-2">
				<a @click="mikrotikConfig.CreateNew = false"
				   :class="{'opacity-50': mikrotikConfig.CreateNew}"
				   class="btn btn-primary border-0" style="flex-basis: 50%">
					<i class="bi bi-check-circle-fill me-2" v-if="!mikrotikConfig.CreateNew"></i>
					<i class="bi bi-circle me-2" v-else></i>
					<strong><LocaleText t="Import Existing"></LocaleText></strong>
				</a>
				<a @click="mikrotikConfig.CreateNew = true"
				   :class="{'opacity-50': !mikrotikConfig.CreateNew}"
				   class="btn btn-success border-0" style="flex-basis: 50%">
					<i class="bi bi-check-circle-fill me-2" v-if="mikrotikConfig.CreateNew"></i>
					<i class="bi bi-circle me-2" v-else></i>
					<strong><LocaleText t="Create New"></LocaleText></strong>
				</a>
			</div>
			<div class="card-footer text-muted">
				<small v-if="!mikrotikConfig.CreateNew">
					<i class="bi bi-info-circle me-1"></i>
					<LocaleText t="Import an existing WireGuard interface from your MikroTik device"></LocaleText>
				</small>
				<small v-else>
					<i class="bi bi-info-circle me-1"></i>
					<LocaleText t="Create a new WireGuard interface on your MikroTik device"></LocaleText>
				</small>
			</div>
		</div>
		
		<!-- MikroTik Connection Settings -->
		<div class="card rounded-3 shadow">
			<div class="card-header">
				<LocaleText t="MikroTik Connection"></LocaleText>
			</div>
			<div class="card-body d-flex flex-column gap-3">
				<!-- Host -->
				<div>
					<label class="form-label">
						<LocaleText t="Host/IP Address"></LocaleText>
						<span class="text-danger">*</span>
					</label>
					<input type="text" 
					       class="form-control" 
					       placeholder="192.168.88.1 or router.local"
					       v-model="mikrotikConfig.MikroTikHost"
					       required>
					<small class="text-muted">
						<LocaleText t="IP address or hostname of your MikroTik router"></LocaleText>
					</small>
				</div>
				
				<!-- Username -->
				<div>
					<label class="form-label">
						<LocaleText t="Username"></LocaleText>
						<span class="text-danger">*</span>
					</label>
					<input type="text" 
					       class="form-control" 
					       placeholder="admin"
					       v-model="mikrotikConfig.MikroTikUsername"
					       required>
				</div>
				
				<!-- Password -->
				<div>
					<label class="form-label">
						<LocaleText t="Password"></LocaleText>
						<span class="text-danger">*</span>
					</label>
					<div class="input-group">
						<input :type="showPassword ? 'text' : 'password'" 
						       class="form-control"
						       v-model="mikrotikConfig.MikroTikPassword"
						       required>
						<button class="btn btn-outline-secondary" 
						        type="button"
						        @click="showPassword = !showPassword">
							<i :class="showPassword ? 'bi-eye-slash' : 'bi-eye'"></i>
						</button>
					</div>
				</div>
				
				<!-- Port and SSL Settings -->
				<div class="row">
					<div class="col-md-4">
						<label class="form-label">
							<LocaleText t="Port"></LocaleText>
							<span class="text-danger">*</span>
						</label>
						<input type="number" 
						       class="form-control" 
						       min="1"
						       max="65535"
						       v-model.number="mikrotikConfig.MikroTikPort"
						       required>
					</div>
					<div class="col-md-4">
						<label class="form-label">
							<LocaleText t="Use SSL/HTTPS"></LocaleText>
						</label>
						<select class="form-select" v-model="mikrotikConfig.MikroTikUseSSL">
							<option :value="true">Yes (HTTPS)</option>
							<option :value="false">No (HTTP)</option>
						</select>
					</div>
					<div class="col-md-4">
						<label class="form-label">
							<LocaleText t="Verify SSL"></LocaleText>
						</label>
						<select class="form-select" v-model="mikrotikConfig.MikroTikVerifySSL">
							<option :value="false">No (Self-signed OK)</option>
							<option :value="true">Yes (Strict)</option>
						</select>
					</div>
				</div>
				
				<!-- Help Text for SSL -->
				<div class="alert alert-info mb-0">
					<small>
						<i class="bi bi-info-circle me-1"></i>
						<strong><LocaleText t="SSL Settings"></LocaleText>:</strong>
						<LocaleText t="MikroTik routers use self-signed certificates by default"></LocaleText>.
						<LocaleText t="Set 'Verify SSL' to 'No' for default MikroTik certificates"></LocaleText>.
					</small>
				</div>
				
				<!-- Test Connection Button -->
				<button type="button" 
				        class="btn btn-primary"
				        :disabled="!isValid || testing"
				        @click="testConnection">
					<span v-if="!testing">
						<i class="bi bi-wifi me-2"></i>
						<LocaleText t="Test Connection"></LocaleText>
					</span>
					<span v-else>
						<span class="spinner-border spinner-border-sm me-2"></span>
						<LocaleText t="Testing..."></LocaleText>
					</span>
				</button>
				
				<!-- Test Result -->
				<div v-if="testResult" class="alert alert-success mb-0">
					<i class="bi bi-check-circle me-2"></i>
					{{testResult}}
					<div v-if="availableInterfaces.length > 0" class="mt-2">
						<strong><LocaleText t="Available WireGuard Interfaces"></LocaleText>:</strong>
						<ul class="mb-0">
							<li v-for="iface in availableInterfaces" :key="iface">{{ iface }}</li>
						</ul>
					</div>
				</div>
				
				<!-- Test Error -->
				<div v-if="testError" class="alert alert-danger mb-0">
					<i class="bi bi-exclamation-triangle me-2"></i>
					{{testError}}
				</div>
			</div>
		</div>
	</div>
</template>

<style scoped>

</style>
