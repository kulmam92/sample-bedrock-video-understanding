LAMBDA_NAME_PREFIX = 'bedrock-mm-'
COGNITO_INVITATION_EMAIL_TITLE = 'Your temporary password for the ##APP_NAME##'
APP_NAME = 'Bedrock Multimodal Understanding'
COGNITO_INVITATION_EMAIL_TEMPLATE = '''
<html>
<head>
<style>
    div.WordSection1 {
        page: WordSection1;
        font-family: "Amazon Ember";
        margin: 0in;
        margin-bottom: .0001pt;
        font-size: 12.0pt;
        font-family: "Calibri", sans-serif;
    }
    span.highlight {
        font-weight: bold;
    }
</style>
</head>
<body lang="EN-US" link="#0563C1" vlink="#954F72">
<div class="WordSection1">
    <h2>
        <span class="highlight">You are invited to access the ##APP_NAME## application.
        </span>
    </h2>
    <br/>
    <p>
        <span style="font-size:13.5pt;font-family:'Amazon Ember',sans-serif;color:#333333">Click on the link below to log into the website.
        </span>
    </p>
    <p>
        <span>
            <a href="https://##CLOUDFRONT_URL##" target="_blank">https://##CLOUDFRONT_URL##</a>
        </span>
    </p>
    <p>
    <span>
        You will need the following username and temporary password provided below to login for the first time.
    </span>
    </p>
    <p>
        <span>User name:
            <b>{username}</b>
        </span>
    </p>
    <p>
        <span>Temporary password:
            <b>{####}</b>
        </span>
    </p>
    <br/>
    <p>
    <span>
    Once you log in with your temporary password, you will be required to create a new password for your account.
    </span>
    </p>
</div>
</body>
</html>
'''