# Agent as a Deployment: Deploying and Registering Custom AI Agents to Customer Projects via Google Cloud Marketplace

**Author**: [Veer Muchandi](mailto:veermuchandi@google.com)  
**Reviewers**:   
---

## 🎯 1\. Purpose of This Approach

This guide outlines the process for Independent Software Vendors (ISVs) and Partners to package, publish, and distribute customer-tenant deployable AI agents through the Google Cloud Marketplace for integration with Gemini Enterprise.

* **Approach**: While native Marketplace product types for deploying agents to customer tenants are in development, this solution leverages the Virtual Machine (VM) product category with Terraform automation.  
* **How it works**: By bundling a lightweight dummy VM and Terraform configuration, your package satisfies standard Marketplace validation rules while provisioning the agent directly into the customer's secure project perimeter (Vertex AI / Agent Engine).

---

## 🏗️ 2\. Building & Packaging the Agent

`[Agent Source Code]`   
              `+`   
 \[Terraform Deployment Scripts\] ──▶ Bundle as .zip ──▶ Upload to Versioned GCS Bucket  
              `+`   
     `[Dummy VM Definition]`

### Steps to Package:

1. Develop the Agent & Agent Card:  
   * Build your agent detailing metadata, capabilities, and OAuth2 authorization endpoints.  
2. Create Deployment Scripts (Terraform):  
   * Write Terraform scripts that automate the provisioning of all required IAM roles, service accounts, and runtime services inside the customer tenant.  
   * Include the minimal dummy VM resource definition required for Marketplace VM pipeline compatibility.  
3. Bundle the Package:  
   * Package your source code, Terraform scripts, and metadata into a single .zip file (referencing the standard [phone\_plan\_shopper\_db.zip](https://drive.google.com/file/d/1KxVJYp4zlEymABySaG9JwBUewEq3rQEu/view?usp=drive_link) template structure and [HOW\_TO\_PACKAGE.md](https://drive.google.com/file/d/1zzj981nd-2wm2nUwpokiRR3aNdAYvDVH/view?usp=drive_link)).  
4. Stage in Google Cloud Storage:  
   * Create a Cloud Storage (GCS) bucket in your publishing GCP project.  
   * Enable Object Versioning on the bucket and upload the .zip package.

---

## 🚀 3\. Publishing the Agent via Producer Portal

The steps are explained in detail in [this document](https://docs.google.com/document/d/1GrWBJAupaTaJUMQ28phs6tUZmxheTfVVULXN7jSc4MA/edit?usp=sharing&resourcekey=0-tldaH9AyjRHm6sm7uXFEaw).

Navigate to Google Cloud Console \> Marketplace \> Producer Portal and follow the configuration steps below:

| Configuration Area | Partner Action / Required Setting |
| ----- | ----- |
| 1\. Product Type | Click Add Product and select Virtual Machine. |
| 2\. Metadata & Info | Add product name, description, documentation links, support contacts, and categorization. |
| 3\. Pricing Model | Leave pricing unconfigured / set to \$0 (Free); keep default trial settings. |
| 4\. Deployment Package | • Create a Licensed VM Image. • Choose Manual Configuration \> Custom UI Deployment. • Set Image Variables to source\_image. • Provide the GCS URL to your uploaded .zip package. |
| 5\. Required IAM Roles | Add the following service roles required for tenant provisioning: • Service Account Admin • Cloud Infrastructure Manager Agent • Vertex AI Administrator • Security Admin • Project IAM Admin • Compute Admin • Service Account User |
| 6\. Validation & Launch | • Run Validate to verify image and script integrity. • Test execution using Deployment Preview. • Submit for review and click Publish. |

 

---

## 🔗 4\. Registering the Agent in Gemini Enterprise

Once published, customers can subscribe and activate the agent within their Gemini Enterprise environment:  
`Step 1: Subscribe on Marketplace`   
   └─▶ Step 2: Vendor Approves Order   
          └─▶ Step 3: Admin gets access to terraform, runs it and registers the agent to Gemini Enterprise   
                 └─▶ Step 4: Configure Auth & User Permissions   
                        └─▶ Step 5: End-User Discovers & Uses Agent

### End-to-End Registration Flow:

1. Customer Marketplace Subscription:  
   * The customer navigates to your listing on Google Cloud Marketplace and clicks Subscribe.  
   * An order request is created in Pending state.  
2. Vendor Order Approval:  
   * The partner/vendor approves the order via Producer Portal / Order Management, moving status to Active.  
3. Run terraform and register agent to Gemini Enterprise:  
   * The customer administrator gets access to the terraform script and runs it to deploy the agent to the customer tenant.  
   * The customer administrator opens Gemini Enterprise \> Governance \> Agents.  
   * Select Add Agent \> Agents via Marketplace and choose the approved agent listing.  
4. Grant User Access & Permissions:  
   * Under the User Permissions tab , the admin assigns individual users or groups access.  
5. End-User Discovery & Execution:  
   * Permitted users will see the agent appear in their Gemini Enterprise Agent Gallery under "From your organization".  
   * On first launch, the user clicks Authorize to complete their OAuth2 authentication flow.

