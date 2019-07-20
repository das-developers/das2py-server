<?xml version="1.0"?>
<xsl:stylesheet version="1.0"
	xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

	<xsl:template match="/">
		<html>
		<head>
		<title>das2 Server</title>
		</head>
		<body>
			<xsl:apply-templates/>
		</body>
		</html>
	</xsl:template>

	<xsl:template match="peers">
		<h1><i>das2</i> Server peers</h1>
		<div>
			<xsl:for-each select="server">
				<h2><xsl:value-of select="name"/></h2>
				<p>
				<img>
					<xsl:attribute name="src"><xsl:value-of select="url"/>?server=logo</xsl:attribute>
				</img>
				<a>
					<xsl:attribute name="href"><xsl:value-of select="url"/></xsl:attribute>
					<xsl:value-of select="url"/>
				</a>
				</p>
				<p><xsl:value-of select="description"/></p>
			</xsl:for-each>
		</div>
	</xsl:template>

</xsl:stylesheet>
